% Blocks World planning by symbolic search, in SWI-Prolog.
%
% This is one of three independent implementations of the domain's transition
% semantics (the others are the Z3 encoding and the Python verifier). Nothing
% here is shared with them, which is what makes a disagreement meaningful.
%
% State representation
% --------------------
% A state is a list of stacks; each stack is a list of blocks ordered bottom
% to top. The list of stacks is kept in standard order of terms by msort/2, so
% that two states that differ only by where their stacks sit on the table are
% literally the same Prolog term. That canonical form is what makes cycle
% detection and goal testing a matter of term equality.
%
% Search strategies
% -----------------
%   iddfs    iterative deepening depth-first search
%   idastar  the same, bounded by f = g + h with an admissible h  (default)
%   bfs      breadth-first with a closed set; can prove unsolvability
%
% All three are optimal. iddfs and idastar are included together so that the
% heuristic can be checked against an unguided baseline: they must always
% return plans of the same length, and tests assert exactly that.
%
% Input is a facts file written by the Python driver. Output is a single line
% of JSON, emitted by the small writer at the bottom so that this file depends
% on nothing beyond library(lists).

:- use_module(library(lists)).

% SWI-Prolog declares `table` as a prefix operator (fx, 1150) for its tabling
% directive. That makes `Source \== table` a syntax error: the reader expects
% an operand after `table` and finds a comma. Since this file uses `table` as
% an ordinary atom naming the table surface, and uses no tabling, the operator
% is removed here. Setting priority 0 is the documented way to undefine one.
:- op(0, fx, table).

:- dynamic block/1.
:- dynamic initial_state/1.
:- dynamic goal_state/1.
:- dynamic table_capacity/1.

% ---------------------------------------------------------------------------
% Instance loading
% ---------------------------------------------------------------------------

load_instance(File) :-
    retractall(block(_)),
    retractall(initial_state(_)),
    retractall(goal_state(_)),
    retractall(table_capacity(_)),
    consult(File).

% ---------------------------------------------------------------------------
% Canonical states
% ---------------------------------------------------------------------------

% canonical(+Stacks, -Canonical) drops empty stacks and sorts the rest.
% msort/2 rather than sort/2: duplicate stacks (e.g. two separate single-block
% stacks that happen to be equal) cannot occur because block names are unique,
% but msort states the intent that nothing is being deduplicated.
canonical(Stacks, Canonical) :-
    exclude(==([]), Stacks, NonEmpty),
    msort(NonEmpty, Canonical).

% supports(+State, -Pairs) maps each block to what it rests on, as a sorted
% list of Block-Support pairs. Support is either a block or the atom `table`.
supports(State, Pairs) :-
    findall(B-S, support_in(State, B, S), Raw),
    msort(Raw, Pairs).

support_in(State, Block, Support) :-
    member(Stack, State),
    stack_support(Stack, table, Block, Support).

stack_support([B|Rest], Below, Block, Support) :-
    (   Block = B, Support = Below
    ;   stack_support(Rest, B, Block, Support)
    ).

% clear_blocks(+State, -Blocks) are the blocks with nothing on top.
clear_blocks(State, Blocks) :-
    findall(Top, (member(Stack, State), last(Stack, Top)), Blocks).

% ---------------------------------------------------------------------------
% Actions
%
% move(Block, Source, Destination) costs 1. Preconditions:
%   - Block is clear
%   - Block rests on Source
%   - Destination is clear, or is the table with a slot free
%   - Destination is neither Block nor Source
% ---------------------------------------------------------------------------

legal_move(State, Capacity, move(Block, Source, table), Next) :-
    clear_blocks(State, Clear),
    member(Block, Clear),
    supports(State, Supports),
    memberchk(Block-Source, Supports),
    Source \== table,                   % already on the table: nowhere new
    length(State, Occupied),
    Occupied < Capacity,                % starting a new stack needs a slot
    apply_move(State, Block, table, Next).

% Stacking one block on another never changes the number of stacks, so the
% table capacity cannot be violated by this clause and is not consulted.
legal_move(State, _Capacity, move(Block, Source, Dest), Next) :-
    clear_blocks(State, Clear),
    member(Block, Clear),
    supports(State, Supports),
    memberchk(Block-Source, Supports),
    member(Dest, Clear),
    Dest \== Block,
    Dest \== Source,
    apply_move(State, Block, Dest, Next).

% apply_move(+State, +Block, +Destination, -Next)
apply_move(State, Block, Dest, Next) :-
    remove_block(State, Block, Stripped),
    (   Dest == table
    ->  Placed = [[Block]|Stripped]
    ;   push_onto(Stripped, Dest, Block, Placed)
    ),
    canonical(Placed, Next).

% remove_block(+Stacks, +Block, -Stacks) takes a clear block off its stack.
remove_block([Stack|Rest], Block, Out) :-
    (   last(Stack, Block)
    ->  once(append(Shorter, [Block], Stack)),
        (   Shorter == []
        ->  Out = Rest                  % the stack is gone, freeing a slot
        ;   Out = [Shorter|Rest]
        )
    ;   remove_block(Rest, Block, Tail),
        Out = [Stack|Tail]
    ).

% push_onto(+Stacks, +Target, +Block, -Stacks) puts Block on top of Target.
push_onto([Stack|Rest], Target, Block, Out) :-
    (   last(Stack, Target)
    ->  append(Stack, [Block], Taller),
        Out = [Taller|Rest]
    ;   push_onto(Rest, Target, Block, Tail),
        Out = [Stack|Tail]
    ).

% ---------------------------------------------------------------------------
% Heuristic
%
% h(S) = the number of blocks resting on something other than what the goal
% asks for. A move changes the support of exactly one block, the one it picks
% up, so one move reduces h by at most 1. Therefore h never exceeds the true
% remaining distance, which is precisely admissibility -- and with an
% admissible h, the first solution found at an f-bound is optimal.
% ---------------------------------------------------------------------------

heuristic(State, GoalSupports, H) :-
    supports(State, Supports),
    include(misplaced(GoalSupports), Supports, Wrong),
    length(Wrong, H).

misplaced(GoalSupports, Block-Support) :-
    memberchk(Block-Wanted, GoalSupports),
    Wanted \== Support.

% ---------------------------------------------------------------------------
% Node accounting
% ---------------------------------------------------------------------------

reset_nodes :- nb_setval(bw_nodes, 0).

count_node :-
    nb_getval(bw_nodes, N),
    N1 is N + 1,
    nb_setval(bw_nodes, N1).

nodes(N) :- nb_getval(bw_nodes, N).

% ---------------------------------------------------------------------------
% Strategy 1: iterative deepening depth-first search
%
% Depth is increased one level at a time, so the first plan found is the
% shortest. Cycles are cut by refusing to revisit any state already on the
% current path, which cannot remove an optimal plan: a plan that revisits a
% state contains a loop, and deleting the loop yields a strictly shorter plan
% to the same goal.
% ---------------------------------------------------------------------------

iddfs(Init, Goal, Cap, MaxDepth, Plan, Reached) :-
    between(0, MaxDepth, Depth),
    Reached = Depth,
    dfs(Init, Goal, Cap, Depth, [Init], Plan),
    !.

dfs(State, State, _, _, _, []) :- !.
dfs(State, Goal, Cap, Depth, Path, [Action|Rest]) :-
    Depth > 0,
    Next is Depth - 1,
    count_node,
    legal_move(State, Cap, Action, Successor),
    \+ memberchk(Successor, Path),
    dfs(Successor, Goal, Cap, Next, [Successor|Path], Rest).

% ---------------------------------------------------------------------------
% Strategy 2: IDA*
%
% Identical to iddfs except that a branch is abandoned as soon as g + h exceeds
% the current bound. The bound starts at h(initial) -- a valid lower bound on
% any plan -- and rises by one each round. Raising it by one rather than to the
% smallest f-value that exceeded it costs some repeated work but keeps the
% argument simple: every plan of length < Bound has been fully examined before
% Bound is reached, so the first plan found is optimal.
% ---------------------------------------------------------------------------

idastar(Init, Goal, Cap, MaxDepth, Plan, Reached) :-
    goal_supports(Goal, GoalSupports),
    heuristic(Init, GoalSupports, H0),
    between(H0, MaxDepth, Bound),
    Reached = Bound,
    fdfs(Init, Goal, GoalSupports, Cap, Bound, 0, [Init], Plan),
    !.

fdfs(State, State, _, _, _, _, _, []) :- !.
fdfs(State, Goal, GoalSupports, Cap, Bound, G, Path, [Action|Rest]) :-
    count_node,
    legal_move(State, Cap, Action, Successor),
    \+ memberchk(Successor, Path),
    G1 is G + 1,
    heuristic(Successor, GoalSupports, H),
    F is G1 + H,
    F =< Bound,
    fdfs(Successor, Goal, GoalSupports, Cap, Bound, G1, [Successor|Path], Rest).

goal_supports(Goal, Supports) :- supports(Goal, Supports).

% ---------------------------------------------------------------------------
% Strategy 3: breadth-first search with a closed set
%
% Slower and hungrier than the two above, but it is the only strategy here
% that can *prove* a problem unsolvable: when the frontier empties, every
% state reachable from the initial state has been seen and none of them was
% the goal. Used to settle unsolvability on restricted-table instances, where
% no sound horizon bound exists.
% ---------------------------------------------------------------------------

bfs(Init, Goal, Cap, MaxDepth, Status, Plan) :-
    (   Init == Goal
    ->  Status = sat, Plan = []
    ;   bfs_loop([node(Init, [])], [Init], Goal, Cap, MaxDepth, 0, Status, Rev),
        (   Status == sat
        ->  reverse(Rev, Plan)
        ;   Plan = []
        )
    ).

% An empty frontier means the reachable state space is exhausted.
bfs_loop([], _, _, _, _, _, unsat, []) :- !.
bfs_loop(_, _, _, _, MaxDepth, Depth, limit, []) :- Depth >= MaxDepth, !.
bfs_loop(Frontier, Closed, Goal, Cap, MaxDepth, Depth, Status, Plan) :-
    expand_level(Frontier, Closed, Goal, Cap, NewClosed, Next, Found),
    (   Found = found(Rev)
    ->  Status = sat, Plan = Rev
    ;   Depth1 is Depth + 1,
        bfs_loop(Next, NewClosed, Goal, Cap, MaxDepth, Depth1, Status, Plan)
    ).

expand_level([], Closed, _, _, Closed, [], none).
expand_level([node(State, Rev)|Rest], Closed, Goal, Cap, OutClosed, Out, Found) :-
    count_node,
    findall(node(Successor, [Action|Rev]),
            ( legal_move(State, Cap, Action, Successor),
              \+ memberchk(Successor, Closed) ),
            Children),
    (   member(node(Goal, WinRev), Children)
    ->  OutClosed = Closed, Out = [], Found = found(WinRev)
    ;   dedup_children(Children, Closed, Kept, Closed1),
        expand_level(Rest, Closed1, Goal, Cap, OutClosed, Tail, Found),
        append(Kept, Tail, Out)
    ).

% Children generated within one level can repeat; keep the first of each.
dedup_children([], Closed, [], Closed).
dedup_children([node(S, R)|Rest], Closed, Kept, OutClosed) :-
    (   memberchk(S, Closed)
    ->  dedup_children(Rest, Closed, Kept, OutClosed)
    ;   Kept = [node(S, R)|More],
        dedup_children(Rest, [S|Closed], More, OutClosed)
    ).

% ---------------------------------------------------------------------------
% Entry point
% ---------------------------------------------------------------------------

run(File, Strategy, MaxDepth, Json) :-
    load_instance(File),
    initial_state(RawInit),
    goal_state(RawGoal),
    table_capacity(Cap),
    canonical(RawInit, Init),
    canonical(RawGoal, Goal),
    reset_nodes,
    statistics(inferences, I0),
    statistics(cputime, C0),
    (   Strategy == bfs
    ->  bfs(Init, Goal, Cap, MaxDepth, Status, Plan),
        Reached = MaxDepth
    ;   Strategy == iddfs
    ->  (   iddfs(Init, Goal, Cap, MaxDepth, Plan, Reached)
        ->  Status = sat
        ;   Status = limit, Plan = [], Reached = MaxDepth
        )
    ;   (   idastar(Init, Goal, Cap, MaxDepth, Plan, Reached)
        ->  Status = sat
        ;   Status = limit, Plan = [], Reached = MaxDepth
        )
    ),
    statistics(inferences, I1),
    statistics(cputime, C1),
    % Global stack in use once the search has finished. This is not a peak
    % figure -- SWI does not expose one here -- so it is reported under a name
    % that says what it actually is. For bfs it tracks the closed set; for the
    % depth-first strategies it stays small, which is the point of them.
    (   catch(statistics(globalused, Global), _, fail)
    ->  true
    ;   Global = -1
    ),
    Inferences is I1 - I0,
    CpuMs is (C1 - C0) * 1000,
    nodes(Nodes),
    length(Plan, Length),
    result_json(Status, Plan, Length, Nodes, Inferences, CpuMs, Reached,
                Strategy, Global, Json).

% Convenience entry point for the native swipl command line.
%
% Matched against the tail of argv, not its head -- see the note on the
% corresponding predicate in tetravex.pl.
main :-
    current_prolog_flag(argv, Argv),
    append(_, [File, Strategy, MaxDepthAtom], Argv),
    atom_number(MaxDepthAtom, MaxDepth),
    run(File, Strategy, MaxDepth, Json),
    write(Json), nl.

% ---------------------------------------------------------------------------
% Minimal JSON writer (fixed output shape, so no library needed)
% ---------------------------------------------------------------------------

result_json(Status, Plan, Length, Nodes, Inf, CpuMs, Reached, Strategy,
            Global, Json) :-
    plan_json(Plan, PlanStr),
    format(atom(Json),
           '{"status":"~w","plan":~w,"length":~w,"stats":{"nodes":~w,"inferences":~w,"cputime_ms":~4f,"bound_reached":~w,"strategy":"~w","global_stack_bytes":~w}}',
           [Status, PlanStr, Length, Nodes, Inf, CpuMs, Reached, Strategy, Global]).

plan_json([], '[]') :- !.
plan_json(Actions, Str) :-
    maplist(action_json, Actions, Parts),
    atomic_list_concat(Parts, ',', Inner),
    format(atom(Str), '[~w]', [Inner]).

action_json(move(Block, From, To), Str) :-
    format(atom(Str), '{"block":"~w","from":"~w","to":"~w"}', [Block, From, To]).
