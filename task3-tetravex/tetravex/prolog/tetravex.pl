% TetraVex as a finite-domain constraint problem, in SWI-Prolog CLP(FD).
%
% This is the counterpart to tetravex/solvers/z3_solver.py and posts the same
% constraints in the same order, so that benchmarking the two compares the
% solvers rather than two different ways of modelling the puzzle.
%
% Decision variables, for each cell of the row-major grid:
%
%   TileAt  - which tile id occupies the cell, 0..N-1
%   RotAt   - quarter-turns clockwise, 0..3 (pinned to 0 when rotation is off)
%   Tops / Rights / Bottoms / Lefts - the resolved symbol on each side
%
% Constraints:
%
%   1. all_distinct(TileAt)                  - placement is a bijection
%   2. tuples_in/2 over the tile table       - links a (tile, rotation) choice
%                                              to the symbols it exposes
%   3. Right(r,c) #= Left(r,c+1), Bottom(r,c) #= Top(r+1,c)
%   4. border equalities, when the instance pins them
%   5. ordering constraints across identical tiles (symmetry breaking)
%
% Input is a facts file written by the Python driver; see load_instance/1.
% Output is a single line of JSON, emitted by the small writer at the bottom
% rather than by library(http/json), so that this file has no dependencies
% beyond library(clpfd) and runs identically under native SWI-Prolog and the
% swipl-wasm build.

:- use_module(library(clpfd)).
:- use_module(library(lists)).
:- use_module(library(pairs)).

:- dynamic dims/2.
:- dynamic symbols/1.
:- dynamic allow_rotation/1.
:- dynamic border_spec/1.
:- dynamic tile/5.

% ---------------------------------------------------------------------------
% Instance loading
% ---------------------------------------------------------------------------

load_instance(File) :-
    retractall(dims(_, _)),
    retractall(symbols(_)),
    retractall(allow_rotation(_)),
    retractall(border_spec(_)),
    retractall(tile(_, _, _, _, _)),
    consult(File).

% ---------------------------------------------------------------------------
% Rotation algebra -- rotate(K, T,R,B,L, T2,R2,B2,L2) turns a tile K
% quarter-turns clockwise. The left edge becomes the new top.
% ---------------------------------------------------------------------------

rotate(0, T, R, B, L, T, R, B, L).
rotate(1, T, R, B, L, L, T, R, B).
rotate(2, T, R, B, L, B, L, T, R).
rotate(3, T, R, B, L, R, B, L, T).

permitted_rotations(Rots) :-
    (   allow_rotation(true)
    ->  Rots = [0, 1, 2, 3]
    ;   Rots = [0]
    ).

% tile_table(-Table) is the relation tuples_in/2 ranges over: every
% (Id, Rotation, Top, Right, Bottom, Left) a tile is allowed to present.
tile_table(Table) :-
    permitted_rotations(Rots),
    findall([Id, K, T2, R2, B2, L2],
            ( tile(Id, T, R, B, L),
              member(K, Rots),
              rotate(K, T, R, B, L, T2, R2, B2, L2) ),
            Table).

% ---------------------------------------------------------------------------
% Model
% ---------------------------------------------------------------------------

model(TileAt, RotAt, edges(Tops, Rights, Bottoms, Lefts)) :-
    dims(Rows, Cols),
    NCells is Rows * Cols,
    TileMax is NCells - 1,
    symbols(S),
    SymMax is S - 1,

    length(TileAt, NCells),
    length(RotAt, NCells),
    length(Tops, NCells),
    length(Rights, NCells),
    length(Bottoms, NCells),
    length(Lefts, NCells),

    % 1. one tile per cell, every tile used exactly once
    TileAt ins 0..TileMax,
    all_distinct(TileAt),

    (   allow_rotation(true)
    ->  RotAt ins 0..3
    ;   RotAt ins 0..0
    ),

    Tops ins 0..SymMax,
    Rights ins 0..SymMax,
    Bottoms ins 0..SymMax,
    Lefts ins 0..SymMax,

    % 2. link the choice of tile and rotation to the exposed symbols
    tile_table(Table),
    cell_tuples(TileAt, RotAt, Tops, Rights, Bottoms, Lefts, Tuples),
    tuples_in(Tuples, Table),

    % 3. adjacency
    adjacency_h(0, Rows, Cols, Rights, Lefts),
    adjacency_v(0, Rows, Cols, Bottoms, Tops),

    % 4. border
    border_constraints(Rows, Cols, Tops, Rights, Bottoms, Lefts),

    % 5. symmetry breaking across identical tiles
    symmetry(TileAt, NCells).

cell_tuples([], [], [], [], [], [], []).
cell_tuples([Ti|Ts], [Ro|Ros], [To|Tos], [Ri|Ris], [Bo|Bos], [Le|Les],
            [[Ti, Ro, To, Ri, Bo, Le]|Rest]) :-
    cell_tuples(Ts, Ros, Tos, Ris, Bos, Les, Rest).

idx(R, C, Cols, I) :- I is R * Cols + C.

% Right edge of (R,C) must equal the left edge of (R,C+1).
adjacency_h(R, Rows, _, _, _) :- R >= Rows, !.
adjacency_h(R, Rows, Cols, Rights, Lefts) :-
    adjacency_h_row(R, 0, Cols, Rights, Lefts),
    R1 is R + 1,
    adjacency_h(R1, Rows, Cols, Rights, Lefts).

adjacency_h_row(_, C, Cols, _, _) :- C >= Cols - 1, !.
adjacency_h_row(R, C, Cols, Rights, Lefts) :-
    C1 is C + 1,
    idx(R, C, Cols, I),
    idx(R, C1, Cols, J),
    nth0(I, Rights, X),
    nth0(J, Lefts, Y),
    X #= Y,
    adjacency_h_row(R, C1, Cols, Rights, Lefts).

% Bottom edge of (R,C) must equal the top edge of (R+1,C).
adjacency_v(R, Rows, _, _, _) :- R >= Rows - 1, !.
adjacency_v(R, Rows, Cols, Bottoms, Tops) :-
    adjacency_v_row(R, 0, Cols, Bottoms, Tops),
    R1 is R + 1,
    adjacency_v(R1, Rows, Cols, Bottoms, Tops).

adjacency_v_row(_, C, Cols, _, _) :- C >= Cols, !.
adjacency_v_row(R, C, Cols, Bottoms, Tops) :-
    R1 is R + 1,
    idx(R, C, Cols, I),
    idx(R1, C, Cols, J),
    nth0(I, Bottoms, X),
    nth0(J, Tops, Y),
    X #= Y,
    C1 is C + 1,
    adjacency_v_row(R, C1, Cols, Bottoms, Tops).

% ---------------------------------------------------------------------------
% Border
% ---------------------------------------------------------------------------

border_constraints(_, _, _, _, _, _) :-
    border_spec(none), !.
border_constraints(Rows, Cols, Tops, Rights, Bottoms, Lefts) :-
    border_spec(border(BT, BR, BB, BL)),
    RowLast is Rows - 1,
    ColLast is Cols - 1,
    pin_row(0, 0, Cols, Tops, BT),
    pin_row(RowLast, 0, Cols, Bottoms, BB),
    pin_col(0, 0, Cols, Rows, Lefts, BL),
    pin_col(ColLast, 0, Cols, Rows, Rights, BR).

% pin_row(+Row, +Col, +Cols, +EdgeVars, +Values)
pin_row(_, C, Cols, _, _) :- C >= Cols, !.
pin_row(R, C, Cols, Edges, Values) :-
    idx(R, C, Cols, I),
    nth0(I, Edges, X),
    nth0(C, Values, V),
    X #= V,
    C1 is C + 1,
    pin_row(R, C1, Cols, Edges, Values).

% pin_col(+Col, +Row, +Cols, +Rows, +EdgeVars, +Values)
pin_col(_, R, _, Rows, _, _) :- R >= Rows, !.
pin_col(C, R, Cols, Rows, Edges, Values) :-
    idx(R, C, Cols, I),
    nth0(I, Edges, X),
    nth0(R, Values, V),
    X #= V,
    R1 is R + 1,
    pin_col(C, R1, Cols, Rows, Edges, Values).

% ---------------------------------------------------------------------------
% Symmetry breaking
%
% Tiles carrying identical edge symbols are interchangeable: swapping them
% yields the same picture. Pin them into increasing cell order so that the
% uniqueness check counts pictures rather than labelled assignments.
%
% Positions are recovered with element/3, which together with all_distinct on
% both lists channels TileAt to its inverse permutation. The channelling is
% only built when duplicates actually exist.
% ---------------------------------------------------------------------------

duplicate_pairs(Pairs) :-
    findall(Sig-Id,
            ( tile(Id, T, R, B, L), Sig = sig(T, R, B, L) ),
            Raw),
    keysort(Raw, Sorted),
    group_pairs_by_key(Sorted, Groups),
    findall(A-B,
            ( member(_-Ids, Groups),
              msort(Ids, Sorted2),
              adjacent_pair(Sorted2, A, B) ),
            Pairs).

adjacent_pair([A, B|_], A, B).
adjacent_pair([_|Rest], A, B) :- adjacent_pair(Rest, A, B).

symmetry(TileAt, NCells) :-
    duplicate_pairs(Pairs),
    (   Pairs == []
    ->  true
    ;   length(Pos, NCells),
        Pos ins 1..NCells,
        all_distinct(Pos),
        channel(0, NCells, TileAt, Pos),
        post_order(Pairs, Pos)
    ).

channel(T, N, _, _) :- T >= N, !.
channel(T, N, TileAt, Pos) :-
    nth0(T, Pos, P),
    element(P, TileAt, T),
    T1 is T + 1,
    channel(T1, N, TileAt, Pos).

post_order([], _).
post_order([A-B|Rest], Pos) :-
    nth0(A, Pos, PA),
    nth0(B, Pos, PB),
    PA #< PB,
    post_order(Rest, Pos).

% ---------------------------------------------------------------------------
% Search
% ---------------------------------------------------------------------------

% solve_grid(-Grid) where Grid is a flat, row-major list of [TileId, Rotation].
solve_grid(Grid) :-
    model(TileAt, RotAt, _),
    append(TileAt, RotAt, Vars),
    labeling([ff], Vars),
    zip_grid(TileAt, RotAt, Grid).

zip_grid([], [], []).
zip_grid([T|Ts], [R|Rs], [[T, R]|Rest]) :- zip_grid(Ts, Rs, Rest).

% At most two solutions, enough to decide uniqueness without enumerating.
first_two(Sols) :-
    findall(G, limit(2, solve_grid(G)), Sols).

% ---------------------------------------------------------------------------
% Entry points. Both return a single JSON string.
% ---------------------------------------------------------------------------

run(File, Mode, Json) :-
    load_instance(File),
    statistics(inferences, I0),
    statistics(cputime, C0),
    (   Mode == unique
    ->  first_two(Sols),
        (   Sols == []
        ->  Status = unsat, Grid = [], Unique = 'null', Second = []
        ;   Sols = [G1]
        ->  Status = sat, Grid = G1, Unique = true, Second = []
        ;   Sols = [G1, G2],
            Status = sat, Grid = G1, Unique = false, Second = G2
        )
    ;   (   solve_grid(G1)
        ->  Status = sat, Grid = G1
        ;   Status = unsat, Grid = []
        ),
        Unique = 'null', Second = []
    ),
    statistics(inferences, I1),
    statistics(cputime, C1),
    Inferences is I1 - I0,
    CpuMs is (C1 - C0) * 1000,
    dims(Rows, Cols),
    result_json(Status, Grid, Second, Unique, Rows, Cols, Inferences, CpuMs, Json).

% Convenience entry point used by the native swipl command line.
%
% Matching the *tail* of argv rather than its head keeps this working whether
% or not the running binary's own name is included in the list, which differs
% between invocation styles.
main :-
    current_prolog_flag(argv, Argv),
    append(_, [File, ModeAtom], Argv),
    run(File, ModeAtom, Json),
    write(Json), nl.

% ---------------------------------------------------------------------------
% Minimal JSON writer (fixed output shape, so no library needed)
% ---------------------------------------------------------------------------

result_json(Status, Grid, Second, Unique, Rows, Cols, Inf, CpuMs, Json) :-
    grid_json(Grid, Rows, Cols, GridStr),
    grid_json(Second, Rows, Cols, SecondStr),
    format(atom(Json),
           '{"status":"~w","grid":~w,"second":~w,"unique":~w,"stats":{"inferences":~w,"cputime_ms":~4f}}',
           [Status, GridStr, SecondStr, Unique, Inf, CpuMs]).

grid_json([], _, _, '[]') :- !.
grid_json(Flat, _Rows, Cols, Str) :-
    chunk(Flat, Cols, RowsList),
    maplist(row_json, RowsList, RowStrs),
    atomic_list_concat(RowStrs, ',', Inner),
    format(atom(Str), '[~w]', [Inner]).

row_json(Row, Str) :-
    maplist(cell_json, Row, Cells),
    atomic_list_concat(Cells, ',', Inner),
    format(atom(Str), '[~w]', [Inner]).

cell_json([T, R], Str) :-
    format(atom(Str), '{"tile":~w,"rot":~w}', [T, R]).

chunk([], _, []) :- !.
chunk(List, N, [Chunk|Rest]) :-
    length(Chunk, N),
    append(Chunk, Tail, List),
    !,
    chunk(Tail, N, Rest).
