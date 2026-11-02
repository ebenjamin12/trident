#!/usr/bin/env python3
import argparse, itertools, random, re, time, sys
from typing import Optional, Dict, Tuple
from enum import Enum

class SolverEngine(Enum):
    Z3_SMT = "Z3 SMT"
    BRUTE_FORCE = "Brute-Force"

def load_words(min_len=3, max_len=6):
    for path in ("/usr/share/dict/words", "/usr/dict/words"):
        try:
            with open(path) as f:
                return [w.strip().upper() for w in f if w.strip().isalpha() and min_len <= len(w.strip()) <= max_len]
        except: pass
    return ["ADD","AND","ANT","ARM","ART","ASH","ASK","BAD","BAG","BAN","BAR","BAT","BED","BIG","BIT","BOX","BOY","BUD","BUG","BUS","BUY","CAN","CAP","CAR","CAT","COP","COT","CUP","CUT","DAD","DAY","DEN","DIG","DIP","DOG","DOT","DUG","EAR","EAT","EGG","END","EYE","FAN","FAR","FAT","FED","FIG","FIT","FUN","GAS","GEM","GUN","GUY","HAM","HAT","HAY","HEN","HIT","HOG","HOP","HOT","HUG","HUM","JAM","JAR","JET","JOB","JOG","JOY","JUG","KID","KIT","LAD","LAP","LAW","LAY","LEG","LID","LIP","LOG","LOT","MAP","MAT","MEN","MET","MOP","MUD","MUG","NAP","NET","NOD","NUN","OAK","OAR","ODD","OWL","OWN","PAD","PAL","PAN","PAR","PAT","PAW","PAY","PEG","PEN","PET","PIG","PIN","PIT","POT","PUB","PUN","PUP","RAG","RAM","RAN","RAP","RAT","RAY","RED","RIB","RIG","RIM","RIP","ROD","ROT","ROW","RUG","RUN","RUT","SAP","SAW","SAY","SEA","SET","SIN","SIP","SIT","SOB","SON","SUM","SUN","TAB","TAN","TAP","TAR","TEN","TIN","TIP","TOE","TON","TOP","TOY","TUB","TUG","WAR","WAX","WAY","WEB","WET","WIG","WIN","WIT","WOE","YAM","YEW","ZAP","ZOO","ABLE","ACID","ALSO","AREA","ARMY","AWAY","BABY","BACK","BAKE","BALL","BAND","BANK","BASE","BEAM","BEAR","BEAT","BELL","BELT","BEND","BEST","BIRD","BITE","BLOW","BLUE","BOAT","BODY","BOLD","BOLT","BONE","BOOK","BORE","BORN","BOWL","BUSH","CAGE","CAKE","CALL","CAME","CAMP","CARD","CARE","CART","CASE","CASH","CAST","CAVE","CHAT","CHIN","CITY","CLAY","COAT","COAL","CODE","COIN","COLD","COME","COOK","COOL","COPE","COPY","CORD","CORE","CORN","COST","CRAB","CREW","CROP","CROW","CUBE","CURE","CUTE","DAMP","DARK","DATE","DAWN","DEAD","DEAL","DEAR","DECK","DEEP","DESK","DIAL","DICE","DIET","DIRT","DISK","DOCK","DOME","DONE","DOOR","DOWN","DRAG","DRAW","DREW","DROP","DRUG","DRUM","DUCK","DULL","DUMP","DUNG","DUNK","DUSK","DUST","DUTY","EACH","EARL","EARN","EASE","EAST","EASY","ECHO","EDGE","EMIT","EVEN","EVER","EVIL","EXAM","FACE","FACT","FADE","FAIL","FAIR","FAKE","FALL","FAME","FAST","FATE","FEAR","FEED","FEEL","FEET","FELL","FELT","FILE","FILL","FILM","FIND","FINE","FIRE","FIRM","FISH","FIST","FIVE","FLAG","FLAT","FLEW","FLIP","FLOW","FOLK","FOND","FOOD","FOOL","FOOT","FORD","FORK","FORM","FORT","FOUL","FOUR","FREE","FROM","FUEL","FULL","FUME","FUND","FUNK","FUSE","GAIN","GALE","GAME","GANG","GATE","GAVE","GEAR","GIFT","GIRL","GIVE","GLAD","GLOW","GLUE","GOAT","GOAL","GOLD","GOLF","GONE","GOOD","GORE","GOWN","GRAB","GRAY","GREW","GRIN","GRIP","GROW","GULF","GUST","HAIR","HALF","HALL","HALT","HAND","HANG","HARD","HARE","HARM","HATE","HAVE","HAWK","HAZE","HEAD","HEAL","HEAP","HEAR","HEAT","HEEL","HEIR","HELD","HELL","HELP","HERD","HERE","HERO","HIGH","HIKE","HILL","HIND","HINT","HIRE","HOLD","HOLE","HOLY","HOME","HOOD","HOOF","HOOK","HOOP","HOPE","HORN","HOSE","HOST","HOUR","HUGE","HULL","HUNG","HUNK","HUNT","HURT","HUSH","HYMN","ICON","IDEA","IDLE","INCH","INTO","IRON","ITEM","JAIL","JOKE","JOLT","JUMP","JUNE","JUNK","JURY","JUST","KEEN","KEEP","KEPT","KICK","KILL","KIND","KING","KISS","KNEE","KNEW","KNIT","KNOT","KNOW","LACE","LACK","LADY","LAID","LAKE","LAMB","LAME","LAMP","LAND","LANE","LANK","LARD","LARK","LAST","LATE","LAWN","LAZY","LEAD","LEAF","LEAK","LEAN","LEAP","LEFT","LEND","LENS","LENT","LESS","LIAR","LICE","LICK","LIED","LIFE","LIFT","LIKE","LILY","LIMB","LIME","LIMP","LINE","LINK","LINT","LION","LIST","LIVE","LOAD","LOAF","LOAN","LOCK","LOFT","LONE","LONG","LOOK","LOOM","LOOP","LOOT","LORD","LORE","LOSE","LOSS","LOST","LOUD","LOUT","LOVE","LUCK","LUMP","LUNG","LURE","LURK","LUSH","LUST","MADE","MAID","MAIL","MAIN","MAKE","MALE","MALL","MANE","MANY","MARE","MARK","MARS","MASH","MASK","MASS","MAST","MATE","MATH","MAZE","MEAL","MEAN","MEAT","MEEK","MEET","MELT","MEMO","MEND","MENU","MESH","MESS","MICE","MILD","MILE","MILK","MILL","MIME","MIND","MINE","MINT","MISS","MIST","MITT","MOAN","MOAT","MOCK","MODE","MOLD","MOLE","MOLT","MONK","MOOD","MOON","MOOR","MOOT","MORE","MOSS","MOST","MOTH","MOVE","MUCH","MULE","MUSE","MUSH","MUST","MUTE","MYTH","NAIL","NAME","NAVY","NEAR","NEAT","NECK","NEED","NEST","NEXT","NICE","NICK","NINE","NODE","NONE","NOON","NOPE","NORM","NOSE","NOTE","NOUN","NULL","OATH","OBEY","OINK","OKAY","ONCE","ONLY","ONTO","OPAL","OPEN","ORAL","ORCA","OVER","PACE","PACK","PAGE","PAID","PAIL","PAIN","PAIR","PALE","PALL","PALM","PANE","PANG","PANT","PARK","PART","PASS","PAST","PATH","PAVE","PAWN","PEAK","PEAR","PEAS","PEAT","PECK","PEEL","PEER","PELT","PENS","PEST","PICK","PIER","PILE","PILL","PINE","PINK","PINT","PIPE","PITY","PLAN","PLAY","PLEA","PLOT","PLOW","PLUM","PLUS","POEM","POET","POKE","POLE","POLL","POND","PONY","POOL","POOR","POPE","PORK","PORT","POSE","POST","POUR","PRAY","PREP","PREY","PRIM","PROD","PROM","PROP","PUFF","PULL","PULP","PUMP","PUNK","PURE","PURR","PUSH","RACE","RACK","RAFT","RAGE","RAID","RAIL","RAIN","RAKE","RAMP","RANG","RANK","RANT","RARE","RASH","RATE","RAVE","READ","REAL","REAP","REAR","REDO","REED","REEL","REIN","RELY","REND","RENT","REST","RICE","RICH","RIDE","RIFE","RIFT","RING","RINK","RIOT","RIPE","RISE","RISK","RITE","ROAD","ROAM","ROAR","ROBE","ROCK","RODE","ROLE","ROLL","ROMP","ROOF","ROOM","ROOT","ROPE","ROSE","ROSY","ROTE","ROUT","ROVE","RUDE","RUIN","RULE","RUMP","RUNG","RUNT","RUSH","RUST","SAFE","SAGA","SAGE","SAID","SAIL","SAKE","SALE","SALT","SAME","SAND","SANE","SANG","SANK","SASH","SAVE","SAWN","SEAL","SEAM","SEAT","SECT","SEED","SEEK","SEEM","SEEN","SELF","SELL","SEMI","SEND","SENT","SERF","SETS","SEWN","SHED","SHIN","SHIP","SHOE","SHOP","SHOT","SHOW","SHUT","SICK","SIDE","SIFT","SIGH","SIGN","SILK","SILL","SILO","SILT","SINE","SING","SINK","SITE","SIZE","SKID","SKIM","SKIN","SLAB","SLAM","SLAP","SLED","SLID","SLIM","SLIP","SLIT","SLOB","SLOP","SLOT","SLOW","SLUG","SLUM","SMOG","SNAP","SNOW","SOAK","SOAP","SOAR","SOCK","SODA","SOFA","SOFT","SOIL","SOLD","SOLE","SOME","SONG","SOON","SOOT","SORE","SORT","SOUL","SOUP","SOUR","SPAM","SPAN","SPEC","SPED","SPIN","SPIT","SPOT","STAB","STAG","STAR","STAY","STEM","STEP","STEW","STIR","STOP","STUB","STUD","SUCH","SUIT","SULK","SUMP","SUNG","SUNK","SURE","SURF","SWAP","SWIM","SWUM","TAIL","TAKE","TALE","TALK","TALL","TAME","TANK","TAPE","TAPS","TARE","TASK","TAUT","TAXI","TEAK","TEAL","TEAM","TEAR","TEEM","TELL","TEMP","TEND","TENT","TERM","TEST","TEXT","THAN","THAT","THAW","THEE","THEM","THEN","THEY","THIN","THIS","THOU","THUD","THUG","TICK","TIDE","TIDY","TIED","TIER","TIES","TILE","TILL","TILT","TIME","TINE","TINT","TINY","TIRE","TOAD","TOES","TOFU","TOIL","TOLD","TOLL","TOMB","TOME","TONE","TOOK","TOOL","TOOT","TOPS","TORE","TORN","TOSS","TOUR","TOUT","TOWN","TOYS","TRAP","TRAY","TREAD","TREE","TREK","TRIM","TRIO","TRIP","TROD","TROT","TRUE","TUBA","TUBE","TUCK","TUFT","TUNA","TUNE","TURF","TURN","TUSK","TUTU","TWIG","TWIN","TYPE","UGLY","UNDO","UNIT","UPON","URGE","USED","USER","VAIN","VALE","VAMP","VANE","VARY","VASE","VAST","VEAL","VEIL","VEIN","VEND","VENT","VERB","VERY","VEST","VETO","VICE","VIEW","VILE","VINE","VISA","VISE","VOID","VOLT","VOTE","WADE","WAGE","WAIL","WAIT","WAKE","WALK","WALL","WAND","WANT","WARD","WARM","WARN","WARP","WARS","WART","WASH","WASP","WAVE","WAVY","WEAK","WEAN","WEAR","WEED","WEEK","WEEP","WELD","WELL","WENT","WEPT","WERE","WEST","WHAM","WHAT","WHEN","WHET","WHEW","WHEY","WHIM","WHIP","WHIZ","WHOM","WICK","WIDE","WIFE","WILD","WILL","WILT","WILY","WIND","WINE","WING","WINK","WIPE","WIRE","WISE","WISH","WITH","WITS","WOKE","WOLF","WOMB","WOOD","WOOL","WORD","WORE","WORK","WORM","WORN","WRAP","WREN","WRIT","YANK","YARD","YARN","YAWN","YEAR","YELL","YELP","YOKE","YOLK","YOUR","ZEAL","ZERO","ZEST","ZINC","ZONE","ZOOM","ABOUT","ABUSE","ADMIT","ADOPT","ADULT","AFTER","AGAIN","AGENT","AGREE","AHEAD","ALARM","ALBUM","ALERT","ALIEN","ALIGN","ALIKE","ALIVE","ALLEY","ALLOW","ALONE","ALONG","ALTER","ANGEL","ANGER","ANGLE","ANGRY","ANKLE","ANNOY","ANTIC","ANVIL","APART","APPLE","APPLY","ARENA","ARGUE","ARISE","ARRAY","ARROW","ASIDE","ASSET","ATLAS","ATTIC","AUDIO","AUDIT","AVOID","AWAKE","AWARD","AWARE","BADLY","BAGEL","BAKER","BEACH","BEAST","BEGIN","BEING","BELOW","BENCH","BILLY","BIRTH","BLACK","BLADE","BLAME","BLANK","BLAST","BLEAK","BLEND","BLESS","BLIND","BLINK","BLISS","BLOCK","BLOOD","BLOOM","BLOWN","BOARD","BOAST","BOGUS","BOOTH","BOUND","BRAIN","BRAKE","BRAND","BRASS","BRAVE","BREAD","BREAK","BREED","BRICK","BRIEF","BRING","BRINK","BROAD","BROKE","BROOK","BROOM","BROTH","BROWN","BRUSH","BUILD","BUILT","BUNCH","BURST","BUYER","CABIN","CABLE","CAMEL","CANAL","CANDY","CANOE","CANON","CARAT","CARGO","CAROL","CARRY","CARVE","CATCH","CAUSE","CEASE","CHAIN","CHAIR","CHALK","CHAMP","CHANT","CHAOS","CHARM","CHART","CHASE","CHEAP","CHEAT","CHECK","CHEEK","CHEER","CHESS","CHEST","CHICK","CHIEF","CHILD","CHINA","CHIRP","CHOKE","CHORD","CHORE","CHOSE","CHUNK","CHURN","CIGAR","CINCH","CIVIC","CIVIL","CLAIM","CLAMP","CLANG","CLASP","CLASS","CLEAN","CLEAR","CLERK","CLICK","CLIFF","CLIMB","CLING","CLOAK","CLOCK","CLONE","CLOSE","CLOTH","CLOUD","CLOUT","CLOWN","COACH","COAST","COCOA","COLON","COMIC","CORAL","COUCH","COUGH","COULD","COUNT","COUPE","COURT","COVER","COWER","CRACK","CRAFT","CRAMP","CRANE","CRANK","CRASH","CRATE","CRAVE","CRAWL","CRAZE","CRAZY","CREAK","CREAM","CREED","CREEK","CREEP","CREPE","CREST","CRIME","CRIMP","CRISP","CROAK","CROCK","CROOK","CROON","CROPS","CROSS","CROUP","CROWD","CROWN","CRUDE","CRUEL","CRUISE","CRUMB","CRUSH","CRUST","CURVE","CUSHY","CYCLE","DAILY","DAIRY","DAISY","DANCE","DANDY","DATED","DEALT","DEATH","DEBIT","DEBUT","DECAY","DECOR","DECOY","DEFER","DELAY","DELTA","DELVE","DEMON","DENIM","DENSE","DEPTH","DERBY","DESIGN","DESIRE","DIARY","DIGIT","DIMLY","DINER","DINGY","DIRTY","DISCO","DITCH","DITTO","DIVAN","DIVER","DIZZY","DODGE","DOGMA","DOING","DOLOR","DONOR","DOUBT","DOUGH","DOZEN","DRAFT","DRAIN","DRAKE","DRAMA","DRANK","DRAPE","DRAWN","DREAD","DREAM","DREAR","DREGS","DRESS","DRIED","DRIFT","DRILL","DRINK","DRIVE","DROLL","DRONE","DROOL","DROOP","DROSS","DROVE","DROWN","DRUGS","DRUMS","DRUNK","DRYLY","DUCKS","DUELS","DULLS","DULLY","DUMMY","DUMPY","DUNCE","DUNES","DUNKS","DUSTY","DUVET","DWARF","DWELL","DWELT","DYING","EAGER","EAGLE","EARLY","EARTH","EASEL","EASED","EATEN","EATER","EAVES","EBONY","ECLAT","EDGED","EDIFY","EDICT","EERIE","EGRET","EIGHT","EJECT","EKING","ELATE","ELBOW","ELDER","ELECT","ELITE","ELOPE","ELUDE","EMBED","EMBER","EMCEE","EMERY","EMOJI","EMOTE","EMPTY","ENACT","ENEMY","ENJOY","ENNUI","ENSUE","ENTER","ENTRY","ENVOY","EPICS","EPOCH","EQUAL","EQUIP","ERASE","ERECT","ERODE","ERROR","ERUPT","ESSAY","ETHER","ETHIC","ETHOS","EVADE","EVENS","EVENT","EVERY","EVICT","EVOKE","EXACT","EXALT","EXCEL","EXERT","EXILE","EXIST","EXPAT","EXPEL","EXTOL","EXTRA","EXUDE","EXULT","FABLE","FACET","FACED","FADED","FAERY","FAINT","FAIRY","FAITH","FAKER","FAKIR","FALLS","FALSE","FAMED","FANCY","FANGS","FARCE","FARED","FARES","FARMS","FATWA","FATTY","FAULT","FAUNA","FAVOR","FAXED","FAZED","FEARS","FEAST","FEATS","FECAL","FEEDS","FEELS","FEIGN","FEINT","FELINE","FELLA","FELON","FELTS","FEMUR","FENCE","FENDS","FERAL","FERNS","FERRY","FETAL","FETCH","FETID","FETUS","FEVER","FEWER","FIBER","FICKLE","FIELD","FIEND","FIERY","FIFTH","FIFTY","FIGHT","FILED","FILER","FILES","FILET","FILLS","FILLY","FILMS","FILMY","FILTH","FINAL","FINCH","FINDS","FINED","FINER","FINES","FINIS","FINITE","FIRED","FIRER","FIRES","FIRMS","FIRST","FISHY","FISTS","FITLY","FIXED","FIXER","FIXES","FIZZY","FJORD","FLACK","FLAGS","FLAIL","FLAIR","FLAKE","FLAKY","FLAME","FLANK","FLAPS","FLARE","FLASH","FLASK","FLATS","FLAWS","FLEAS","FLECK","FLEES","FLEET","FLESH","FLEWS","FLICK","FLIED","FLIER","FLIES","FLING","FLINT","FLIPS","FLIRT","FLITS","FLOAT","FLOCK","FLOOD","FLOOR","FLORA","FLOSS","FLOUR","FLOUT","FLOWN","FLOWS","FLUBS","FLUES","FLUFF","FLUID","FLUKE","FLUNG","FLUNK","FLUSH","FLUTE","FOAMS","FOAMY","FOCAL","FOCUS","FOGEY","FOILS","FOIST","FOLDS","FOLIO","FOLKS","FOLLY","FONTS","FOODS","FOOLS","FOOTS","FORAY","FORCE","FORDS","FOREX","FORGE","FORGO","FORKS","FORMS","FORTE","FORTH","FORTY","FORUM","FOSSE","FOUND","FOUNT","FOURS","FOWLS","FOXES","FOYER","FRAIL","FRAME","FRANK","FRAUD","FRAYS","FREAK","FREES","FRESH","FRETS","FRIAR","FRIED","FRIES","FRILL","FRISK","FRITZ","FROCK","FROGS","FROND","FRONT","FROST","FROTH","FROWN","FROZE","FRUIT","FRUMP","FUDGE","FUELS","FUGUE","FULLY","FUMED","FUMES","FUNDS","FUNGI","FUNKS","FUNNY","FURZE","FUSED","FUSES","FUSSY","FUSTY","FUZZY","GABLE","GAFFE","GAILY","GAINS","GAITS","GALES","GALLS","GALOP","GAMES","GAMMA","GANGS","GANJA","GAPES","GARBS","GAILY","GARLIC","GARNI","GASH","GASPS","GASSY","GATED","GATES","GAUGE","GAUNT","GAUZE","GAUZY","GAVEL","GAWKS","GAWKY","GAWPED","GAYER","GAYLY","GAZED","GAZER","GAZES","GEARED","GEARS","GEESE","GELID","GELLED","GEMS","GENES","GENIE","GENTS","GENUS","GERMS","GESTS","GETUP","GHAST","GHATS","GHEES","GHOST","GHOUL","GIANT","GIBED","GIBER","GIBES","GIDDY","GIFTS","GILDS","GILLS","GILTS","GIMPS","GINGE","GINKS","GIPSY","GIRDS","GIRLS","GIRLY","GIRTS","GIRTH","GISMO","GISTS","GIVEN","GIVER","GIVES","GIZMO","GLADE","GLADS","GLAND","GLANS","GLARE","GLARY","GLASS","GLAZE","GLAZY","GLEAM","GLEAN","GLEBA","GLEBE","GLEED","GLEEK","GLEES","GLEET","GLENS","GLENT","GLEYS","GLIAL","GLIAS","GLIDE","GLIDER","GLIFF","GLIM","GLIMS","GLINT","GLINY","GLIRE","GLISH","GLISK","GLIST","GLITZ","GLIVE","GLOAM","GLOAT","GLOB","GLOBE","GLOBS","GLOBY","GLODE","GLOME","GLOMS","GLOMP","GLONK","GLOOM","GLOON","GLOOT","GLOPE","GLOPS","GLORY","GLORS","GLOSS","GLOSSY","GLOST","GLOTS","GLOTT","GLOUT","GLOVE","GLOVED","GLOVER","GLOVES","GLOWS","GLOWED","GLOWER","GLOWTH","GLOWY","GLUBE","GLUCAN","GLUCOSE","GLUCK","GLUED","GLUER","GLUES","GLUEY","GLUFF","GLUG","GLUMM","GLUMPY","GLUMS","GLUMY","GLUNCH","GLUNG","GLUNK","GLUO","GLUPO","GLURGE","GLURL","GLURN","GLURS","GLUSH","GLUSK","GLUTE","GLUTS","GLUTZ","GNAFF","GNAGS","GNAIL","GNAMS","GNAMT","GNARD","GNARR","GNARS","GNARL","GNARLS","GNASH","GNAST","GNATS","GNAUR","GNAUP","GNAUS","GNAWB","GNAWED","GNAWER","GNAWES","GNAWS","GNAWY","GNAFF","GNAGS","GNAIL","GNAMS","GNAMT","GNARD","GNARR","GNARS","GNARL","GNARLS","GNASH","GNAST","GNATS","GNAUR","GNAUP","GNAUS","GNAWB","GNAWED","GNAWER","GNAWES","GNAWS","GNAWY"]

WORDS = load_words()
WORD_SET = set(WORDS)
BY_LEN = {i: [w for w in WORDS if len(w) == i] for i in range(3, 7)}

print(f"\n{'='*70}\n{'CRYPTARITHM SOLVER - INITIALIZATION':^70}\n{'='*70}")
print(f"Dictionary: {len(WORDS)} words loaded")
print(f"Word distribution: 3-letter: {len(BY_LEN.get(3, []))}, 4-letter: {len(BY_LEN.get(4, []))}, 5-letter: {len(BY_LEN.get(5, []))}\n")

def detect_solver_engine():
    try:
        import z3
        return SolverEngine.Z3_SMT
    except:
        return SolverEngine.BRUTE_FORCE

def solve_z3(w1, w2, w3):
    try:
        import z3
        letters = sorted(set(w1 + w2 + w3))
        if len(letters) > 10 or len(letters) < 2:
            return None
        leading = {w1[0], w2[0], w3[0]}
        s = z3.Solver()
        vs = {c: z3.Int(c) for c in letters}
        for v in vs.values():
            s.add(v >= 0, v <= 9)
        for c in leading:
            s.add(vs[c] != 0)
        s.add(z3.Distinct(list(vs.values())))
        def val(word):
            e = z3.IntVal(0)
            for c in word:
                e = e * 10 + vs[c]
            return e
        s.add(val(w1) + val(w2) == val(w3))
        if s.check() == z3.sat:
            m = s.model()
            return {c: m[v].as_long() for c, v in vs.items()}
        return None
    except:
        return None

def solve_brute_force(w1, w2, w3):
    letters = sorted(set(w1 + w2 + w3))
    if len(letters) > 10 or len(letters) < 2:
        return None
    leading = {w1[0], w2[0], w3[0]}
    for perm in itertools.permutations(range(10), len(letters)):
        mp = dict(zip(letters, perm))
        if any(mp[c] == 0 for c in leading):
            continue
        n1 = int("".join(str(mp[c]) for c in w1))
        n2 = int("".join(str(mp[c]) for c in w2))
        n3 = int("".join(str(mp[c]) for c in w3))
        if n1 + n2 == n3:
            return mp
    return None

def solve(w1, w2, w3):
    result = solve_z3(w1, w2, w3)
    return result if result else solve_brute_force(w1, w2, w3)

def generate(seed=None):
    rng = random.Random(seed)
    for _ in range(20000):
        w1 = rng.choice(BY_LEN.get(rng.randint(3, 5), [""]))
        w2 = rng.choice(BY_LEN.get(rng.randint(3, 5), [""]))
        if not w1 or not w2 or len(set(w1 + w2)) > 9:
            continue
        avail = list(range(10))
        rng.shuffle(avail)
        mp = dict(zip(sorted(set(w1 + w2)), avail[:len(set(w1 + w2))]))
        for lead in [w1[0], w2[0]]:
            if mp[lead] == 0 and any(d != 0 and c != lead for c, d in mp.items()):
                swap = next(c for c, d in mp.items() if d != 0 and c != lead)
                mp[lead], mp[swap] = mp[swap], mp[lead]
        if any(mp[c] == 0 for c in [w1[0], w2[0]]):
            continue
        n1, n2 = int("".join(str(mp[c]) for c in w1)), int("".join(str(mp[c]) for c in w2))
        total = str(n1 + n2)
        if total[0] == "0" or len(total) < max(len(w1), len(w2)):
            continue
        rev = {d: c for c, d in mp.items()}
        used, extra, cand, ok = set(mp), {}, [], True
        for ch in total:
            d = int(ch)
            if d in rev:
                cand.append(rev[d])
            else:
                nl = next((c for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" if c not in used and c not in extra), None)
                if not nl:
                    ok = False
                    break
                extra[nl] = d
                rev[d] = nl
                cand.append(nl)
        if not ok:
            continue
        w3 = "".join(cand)
        if w3 not in WORD_SET or w3 in (w1, w2):
            continue
        full = {**mp, **extra}
        if len(set(full.values())) == len(full):
            return w1, w2, w3
    return None

def display_puzzle(w1, w2, w3, mp):
    W = max(len(w1), len(w2), len(w3)) + 2
    bar = "  " + "─" * (W + 1)
    print(f"\n  {w1.rjust(W)}\n+ {w2.rjust(W)}\n{bar}\n= {w3.rjust(W)}")
    if mp:
        def n(w):
            return int("".join(str(mp[c]) for c in w))
        n1, n2, n3 = n(w1), n(w2), n(w3)
        print(f"\n  {str(n1).rjust(W)}\n+ {str(n2).rjust(W)}\n{bar}\n= {str(n3).rjust(W)}")
        print("\n  " + "  ".join(f"{c}={mp[c]}" for c in sorted(mp)))
        print(f"\n  Verification: {n1} + {n2} = {n3} {'✓ Correct!' if n1+n2==n3 else '✗ Error'}")
    else:
        print("\n  ✗ No solution exists.")

def mode_generate():
    print("\n" + "="*70 + f"\n{'GENERATE PUZZLE MODE':^70}\n" + "="*70)
    print("\nGenerating puzzle...")
    t0 = time.perf_counter()
    puzzle = generate()
    if not puzzle:
        print("✗ Failed to generate.")
        return
    w1, w2, w3 = puzzle
    print(f"✓ Generated in {time.perf_counter()-t0:.3f}s\nSolving...")
    t0 = time.perf_counter()
    mp = solve(w1, w2, w3)
    print(f"✓ Solved in {time.perf_counter()-t0:.3f}s")
    display_puzzle(w1, w2, w3, mp)
    print("\n" + "-"*70 + "\nPUZZLE STATISTICS\n" + "-"*70)
    print(f"Word 1: {w1} ({len(w1)} letters)\nWord 2: {w2} ({len(w2)} letters)\nResult: {w3} ({len(w3)} letters)")
    print(f"Total unique letters: {len(set(w1+w2+w3))}\nConstraint complexity: ~{10**len(set(w1+w2+w3)):,} search space")

def mode_custom():
    print("\n" + "="*70 + f"\n{'CUSTOM PUZZLE MODE':^70}\n" + "="*70)
    w1 = input("\nWord 1: ").strip().upper()
    w2 = input("Word 2: ").strip().upper()
    w3 = input("Result: ").strip().upper()
    if not (w1.isalpha() and w2.isalpha() and w3.isalpha()):
        print("✗ Letters only!")
        return
    if len(set(w1+w2+w3)) > 10:
        print("✗ Too many unique letters (max 10).")
        return
    print(f"\n{w1} + {w2} = {w3}\nEnter mapping (e.g. A=1 B=2) or 'SOLVE':")
    inp = input().strip().upper()
    if inp == "SOLVE":
        mp = solve(w1, w2, w3)
        display_puzzle(w1, w2, w3, mp)
        return
    try:
        mp = {p.split('=')[0].strip(): int(p.split('=')[1].strip()) for p in inp.split()}
        all_letters = set(w1+w2+w3)
        if not all(c in mp for c in all_letters):
            print("✗ Missing letters!")
            return
        if len(set(mp.values())) != len(mp) or any(d<0 or d>9 for d in mp.values()):
            print("✗ Invalid mapping!")
            return
        if any(mp[c]==0 for c in {w1[0], w2[0], w3[0]}):
            print("✗ Leading zeros not allowed!")
            return
        def val(w):
            return int("".join(str(mp[c]) for c in w))
        print(f"\n✓ {val(w1)} + {val(w2)} = {val(w1)+val(w2)}\n🎉 Correct!" if val(w1)+val(w2)==val(w3) else f"\n✗ Incorrect")
    except Exception as e:
        print(f"✗ Error: {e}")

def mode_tests():
    print("\n" + "="*70 + f"\n{'AUTOMATED TESTS':^70}\n" + "="*70 + "\n")
    tests = [("SEND+MORE=MONEY","SEND","MORE","MONEY",True),("TWO+TWO=FOUR","TWO","TWO","FOUR",True),("CROSS+ROADS=DANGER","CROSS","ROADS","DANGER",True),("A+B=C","A","B","C",True),("AA+B=AC","AA","B","AC",True),("ABCD+EFGH=IJKL","ABCD","EFGH","IJKL",False),("ONE+ONE=MANY","ONE","ONE","MANY",True),("SIX+TEN=SIX","SIX","TEN","SIX",False),("ART+ART=CART","ART","ART","CART",False)]
    passed = failed = 0
    for i, (name, w1, w2, w3, expect) in enumerate(tests, 1):
        print(f"Test {i}: {name}")
        t0 = time.perf_counter()
        mp = solve(w1, w2, w3)
        elapsed = time.perf_counter() - t0
        has_sol = mp is not None
        if has_sol == expect:
            if has_sol:
                def val(w):
                    return int("".join(str(mp[c]) for c in w))
                if val(w1) + val(w2) == val(w3):
                    print(f"✓ PASS ({elapsed:.4f}s)\n")
                    passed += 1
                else:
                    print(f"✗ FAIL (arithmetic)\n")
                    failed += 1
            else:
                print(f"✓ PASS - unsolvable ({elapsed:.4f}s)\n")
                passed += 1
        else:
            print(f"✗ FAIL\n")
            failed += 1
    print("="*70)
    print(f"Results: {passed} passed, {failed} failed, {100*passed/(passed+failed):.0f}% success")
    print("="*70)

def main():
    engine = detect_solver_engine()
    print(f"\n{'='*70}\nCRYPTARITHM SOLVER\n{'='*70}\nEngine: {engine.value}\n{'='*70}\n")
    while True:
        print("  [1] Generate Puzzle\n  [2] Custom Puzzle\n  [3] Automated Tests\n  [0] Exit\n")
        choice = input("Choice [0-3]: ").strip()
        if choice == "0":
            print("\n" + "="*70 + "\nThank you for using Cryptarithm Solver!\n" + "="*70 + "\n")
            sys.exit(0)
        elif choice == "1":
            mode_generate()
        elif choice == "2":
            mode_custom()
        elif choice == "3":
            mode_tests()
        else:
            print("✗ Invalid choice.\n")
        print("Press Enter to continue...", end="")
        input()

if __name__ == "__main__":
    main()