module Main where

import Data.Char (isUpper, isLower, isAlpha, ord, chr, toLower)
import Data.List (sortBy)
import Data.Ord (comparing)
import Data.Maybe (fromMaybe)
import System.IO (hSetEncoding, hSetBuffering, stdout, utf8, BufferMode(NoBuffering))

shiftChar :: Int -> Char -> Char
shiftChar n c
  | isUpper c = chr (((ord c - ord 'A' + n) `mod` 26) + ord 'A')
  | isLower c = chr (((ord c - ord 'a' + n) `mod` 26) + ord 'a')
  | otherwise = c

caesarEncrypt :: Int -> String -> String
caesarEncrypt key = map (shiftChar key)

caesarDecrypt :: Int -> String -> String
caesarDecrypt key = caesarEncrypt (negate key)

keyShifts :: String -> [Int]
keyShifts key = cycle [ord (toLower k) - ord 'a' | k <- key, isAlpha k]

vigenereEncrypt :: String -> String -> String
vigenereEncrypt key = go (keyShifts key)
  where
    go _ [] = []
    go ks (c:cs) | isAlpha c = shiftChar (head ks) c : go (tail ks) cs
                 | otherwise = c : go ks cs

vigenereDecrypt :: String -> String -> String
vigenereDecrypt key = go (keyShifts key)
  where
    go _ [] = []
    go ks (c:cs) | isAlpha c = shiftChar (negate (head ks)) c : go (tail ks) cs
                 | otherwise = c : go ks cs

englishFreq :: [(Char, Double)]
englishFreq = [('a',8.17),('b',1.49),('c',2.78),('d',4.25),('e',12.70),('f',2.23),('g',2.02),('h',6.09),('i',6.97),('j',0.15),('k',0.77),('l',4.03),('m',2.41),('n',6.75),('o',7.51),('p',1.93),('q',0.10),('r',5.99),('s',6.33),('t',9.06),('u',2.76),('v',0.98),('w',2.36),('x',0.15),('y',1.97),('z',0.07)]

letterCounts :: String -> [(Char, Int)]
letterCounts text = [(c, length (filter (== c) lowered)) | c <- ['a'..'z']]
  where lowered = map toLower (filter isAlpha text)

letterFrequencies :: String -> [(Char, Double)]
letterFrequencies text = [(c, if total == 0 then 0 else (fromIntegral n / fromIntegral total) * 100) | (c, n) <- letterCounts text]
  where total = length (filter isAlpha text)

chiSquared :: String -> Int -> Double
chiSquared ciphertext shift = sum [stat c | c <- ['a'..'z']]
  where
    decoded = caesarDecrypt shift ciphertext
    counts = letterCounts decoded
    total = length (filter isAlpha decoded)
    stat c = let observed = fromIntegral (fromMaybe 0 (lookup c counts)) :: Double
                 expected = (fromMaybe 0 (lookup c englishFreq) / 100) * fromIntegral total
             in if expected == 0 then 0 else (observed - expected) ^ (2 :: Int) / expected

crackCaesar :: String -> [(Int, Double)]
crackCaesar ciphertext = sortBy (comparing snd) [(k, chiSquared ciphertext k) | k <- [0..25]]

-- Kasiski Examination for Vigenere Cipher
nub' :: Eq a => [a] -> [a]
nub' = foldr (\x acc -> if x `elem` acc then acc else x:acc) []

findNgrams :: Int -> String -> [(String, [Int])]
findNgrams n text = [(ngram, positions ngram text) | ngram <- ngramsSet]
  where
    ngramsSet = nub' [take n (drop i text) | i <- [0..(length text - n)]]

positions :: String -> String -> [Int]
positions pattern text = [i | i <- [0..(length text - length pattern)], take (length pattern) (drop i text) == pattern]

kasiskiEstimate :: String -> [(Int, Int)]
kasiskiEstimate ciphertext = 
  let ngrams = findNgrams 3 (filter isAlpha ciphertext)
      repeatedNgrams = [(ng, pos) | (ng, pos) <- ngrams, length pos > 1]
      distances = concat [[p1 - p2 | p1 <- pos, p2 <- pos, p1 > p2] | (_, pos) <- repeatedNgrams]
  in if null distances
     then [(1, 0)]
     else let divisors = nub' (concatMap (\d -> [i | i <- [1..d], d `mod` i == 0]) distances)
              freqs = [(d, length (filter (\x -> x `mod` d == 0) distances)) | d <- divisors, d > 1]
          in sortBy (comparing (negate . snd)) freqs

fmt :: Double -> String
fmt d = take 6 (show d)

modeCaesar :: IO ()
modeCaesar = do
  putStrLn "\n" >> putStrLn (replicate 70 '=') >> putStrLn "CAESAR CIPHER" >> putStrLn (replicate 70 '=')
  putStrLn "\nChoose an option:\n  1. Encrypt\n  2. Decrypt"
  putStr "\nEnter choice [1-2]: "
  op <- getLine
  case op of
    "1" -> do
      putStr "Enter plaintext: "
      text <- getLine
      putStr "Enter shift key (number 0-25): "
      key <- readLn
      putStrLn ""
      putStrLn $ "Plaintext:  " ++ text
      putStrLn $ "Key:        " ++ show key
      putStrLn $ "Encrypted:  " ++ caesarEncrypt key text
    "2" -> do
      putStr "Enter ciphertext: "
      text <- getLine
      putStr "Enter shift key (number 0-25): "
      key <- readLn
      putStrLn ""
      putStrLn $ "Ciphertext: " ++ text
      putStrLn $ "Key:        " ++ show key
      putStrLn $ "Decrypted:  " ++ caesarDecrypt key text
    _ -> putStrLn "Invalid choice."

modeVigenere :: IO ()
modeVigenere = do
  putStrLn "\n" >> putStrLn (replicate 70 '=') >> putStrLn "VIGENERE CIPHER" >> putStrLn (replicate 70 '=')
  putStrLn "\nChoose an option:\n  1. Encrypt\n  2. Decrypt"
  putStr "\nEnter choice [1-2]: "
  op <- getLine
  case op of
    "1" -> do
      putStr "Enter plaintext: "
      text <- getLine
      putStr "Enter keyword (word with letters): "
      key <- getLine
      putStrLn ""
      putStrLn $ "Plaintext:  " ++ text
      putStrLn $ "Key:        " ++ key
      putStrLn $ "Encrypted:  " ++ vigenereEncrypt key text
    "2" -> do
      putStr "Enter ciphertext: "
      text <- getLine
      putStr "Enter keyword (word with letters): "
      key <- getLine
      putStrLn ""
      putStrLn $ "Ciphertext: " ++ text
      putStrLn $ "Key:        " ++ key
      putStrLn $ "Decrypted:  " ++ vigenereDecrypt key text
    _ -> putStrLn "Invalid choice."

modeFrequency :: IO ()
modeFrequency = do
  putStrLn "\n" >> putStrLn (replicate 70 '=') >> putStrLn "FREQUENCY ANALYSIS" >> putStrLn (replicate 70 '=')
  putStr "\nEnter ciphertext to analyse: "
  text <- getLine
  let ranked = crackCaesar text
      top3 = take 3 ranked
      best = fst (head ranked)
      freqs = take 5 $ sortBy (comparing (negate . snd)) (letterFrequencies text)
  putStrLn ""
  putStrLn $ "Ciphertext: " ++ text
  putStrLn $ "Total letters: " ++ show (length (filter isAlpha text))
  putStrLn "\nTop 3 candidate shifts (lower score = better match):"
  mapM_ (\(k, s) -> putStrLn $ "  shift=" ++ show k ++ "  score=" ++ fmt s) top3
  putStrLn $ "\nBest guess (shift=" ++ show best ++ "):"
  putStrLn $ "Plaintext: " ++ caesarDecrypt best text
  putStrLn "\nLetter frequencies in ciphertext (top 5):"
  mapM_ (\(c, f) -> putStrLn $ "  " ++ [c] ++ ": " ++ fmt f ++ "%") freqs

modeKasiski :: IO ()
modeKasiski = do
  putStrLn "\n" >> putStrLn (replicate 70 '=') >> putStrLn "KASISKI EXAMINATION" >> putStrLn (replicate 70 '=')
  putStr "\nEnter Vigenere ciphertext to analyse: "
  text <- getLine
  let alphabetic = filter isAlpha text
      candidates = kasiskiEstimate alphabetic
      top5 = take 5 candidates
  putStrLn ""
  putStrLn $ "Ciphertext: " ++ text
  putStrLn $ "Total letters: " ++ show (length alphabetic)
  if length alphabetic < 50
    then putStrLn "\n⚠ Warning: Text too short for reliable Kasiski analysis (need 50+ letters)"
    else putStrLn ""
  putStrLn "Estimated key lengths (ranked by evidence):"
  if null top5 || (length top5 == 1 && snd (head top5) == 0)
    then putStrLn "  No repeating sequences found. Try a longer ciphertext."
    else mapM_ (\(len, freq) -> putStrLn $ "  Key length " ++ show len ++ ": " ++ show freq ++ " supporting distances") top5
  putStrLn "\nTip: Most frequent key length is likely correct, or test top 3 candidates."

data TestResult = TR String Bool String

printTest :: TestResult -> IO ()
printTest (TR name result msg) = putStrLn $ (if result then "✓ PASS" else "✗ FAIL") ++ " | " ++ name ++ " | " ++ msg

runTests :: [TestResult]
runTests =
  [ TR "Caesar Basic" (caesarEncrypt 3 "hello" == "khoor") "encrypt 'hello' with shift 3"
  , TR "Caesar Roundtrip" (caesarDecrypt 5 (caesarEncrypt 5 "hello") == "hello") "decrypt matches original"
  , TR "Caesar Uppercase" (caesarEncrypt 1 "ABC" == "BCD") "uppercase preserved"
  , TR "Caesar Mixed" (caesarEncrypt 2 "Hello, World!" == "Jgnnq, Yqtnf!") "punctuation preserved"
  , TR "Caesar Empty" (caesarEncrypt 5 "" == "") "empty string handled"
  , TR "Caesar Numbers" (caesarEncrypt 3 "abc123xyz" == "def123abc") "numbers preserved"
  , TR "Caesar Wrap" (caesarEncrypt 1 "xyz" == "yza") "wraps correctly"
  , TR "Vigenere Basic" (vigenereEncrypt "key" "hello" == "rijvs") "encrypt with key"
  , TR "Vigenere Roundtrip" (vigenereDecrypt "secret" (vigenereEncrypt "secret" "attackatdawn") == "attackatdawn") "decrypt matches"
  , TR "Vigenere Case" (vigenereEncrypt "Key" "Hello" == "Rijvs") "case preserved"
  , TR "Vigenere Numbers" (vigenereEncrypt "key" "abc123xyz" == "kfa123hcx") "numbers preserved"
  , TR "Vigenere Empty" (vigenereEncrypt "key" "" == "") "empty string handled"
  , TR "Vigenere Repeat" (vigenereEncrypt "abc" "aaaaaa" == "abcabc") "pattern cycles"
  , TR "Frequency English" (fst (head (crackCaesar (caesarEncrypt 3 "thequickbrownfoxjumpsoverthelazydog"))) == 3) "detected shift"
  , TR "Frequency Shift" (fst (head (crackCaesar (caesarEncrypt 7 "attackatdawn"))) == 7) "shift detected"
  , TR "Frequency Large" (fst (head (crackCaesar (caesarEncrypt 5 (concat (replicate 10 "thequickbrownfoxjumpsoverthelazydog"))))) == 5) "works on large text"
  , TR "Edge Single" (caesarEncrypt 1 "a" == "b") "single char"
  , TR "Edge Space" (caesarEncrypt 3 "   " == "   ") "spaces preserved"
  , TR "Edge Special" (caesarEncrypt 2 "!@#$%" == "!@#$%") "special chars preserved"
  , TR "Edge Negative" (caesarDecrypt (-3) (caesarEncrypt (-3) "hello") == "hello") "negative shift works"
  , TR "Consistency" (caesarEncrypt 5 "thequickbrownfox" == caesarEncrypt 5 "thequickbrownfox") "same input = same output"
  , TR "Kasiski Repeating" (case kasiskiEstimate "ABCABCABCABCABCABC" of [] -> False; candidates -> fst (head candidates) == 3) "identifies ABC pattern (key length 3)"
  , TR "Kasiski No Repeats" (kasiskiEstimate "ABCDEFGHIJKLMNOPQRST" == [(1, 0)]) "returns [(1,0)] for non-repeating"
  , TR "Kasiski Returns List" (not (null (kasiskiEstimate "ATTACKATTACKATTACK"))) "returns non-empty list"
  , TR "Kasiski Long Text" (case kasiskiEstimate (concat (replicate 3 "ABCDEFGHIJ")) of [] -> False; candidates -> snd (head candidates) > 0) "works on longer texts"
  ]

modeTests :: IO ()
modeTests = do
  putStrLn "\n" >> putStrLn (replicate 70 '=') >> putStrLn "AUTOMATED TESTING SUITE" >> putStrLn (replicate 70 '=') >> putStrLn ""
  mapM_ printTest runTests
  let passCount = length (filter (\(TR _ r _) -> r) runTests)
      total = length runTests
  putStrLn ""
  putStrLn (replicate 70 '=')
  putStrLn "TEST SUMMARY"
  putStrLn (replicate 70 '=')
  putStrLn $ "Total tests: " ++ show total
  putStrLn $ "✓ Passed: " ++ show passCount
  putStrLn $ "✗ Failed: " ++ show (total - passCount)
  putStrLn $ "Success rate: " ++ fmt (fromIntegral passCount / fromIntegral total * 100) ++ "%"
  putStrLn (replicate 70 '=')

mainLoop :: IO ()
mainLoop = do
  putStrLn "\n" >> putStrLn (replicate 70 '=') >> putStrLn "SIMPLE CRYPTOGRAPHY TOOL" >> putStrLn (replicate 70 '=')
  putStrLn "\nSelect an option:\n\n  [1] Caesar Cipher\n      Encrypt/decrypt with a numeric shift key\n\n  [2] Vigenere Cipher\n      Encrypt/decrypt with a word key\n\n  [3] Frequency Analysis\n      Crack Caesar cipher using letter frequencies\n\n  [4] Automated Tests\n      Run comprehensive test suite with edge cases\n\n  [5] Kasiski Examination\n      Estimate Vigenere key length using repeated sequences\n\n  [0] Exit\n      Quit the program\n"
  putStr "Enter your choice [0-5]: "
  choice <- getLine
  case choice of
    "0" -> putStrLn "\n" >> putStrLn (replicate 70 '=') >> putStrLn "Thank you for using Simple Cryptography Tool!" >> putStrLn (replicate 70 '=') >> putStrLn ""
    "1" -> modeCaesar >> putStr "\nPress Enter to continue..." >> getLine >> mainLoop
    "2" -> modeVigenere >> putStr "\nPress Enter to continue..." >> getLine >> mainLoop
    "3" -> modeFrequency >> putStr "\nPress Enter to continue..." >> getLine >> mainLoop
    "4" -> modeTests >> putStr "\nPress Enter to continue..." >> getLine >> mainLoop
    "5" -> modeKasiski >> putStr "\nPress Enter to continue..." >> getLine >> mainLoop
    _ -> putStrLn "\n✗ Invalid choice. Please enter 0, 1, 2, 3, 4, or 5." >> putStr "Press Enter to continue..." >> getLine >> mainLoop

main :: IO ()
main = do
  -- Tick/cross/warning glyphs need UTF-8; without this the program crashes
  -- on systems whose default locale is not UTF-8.
  hSetEncoding stdout utf8
  -- Prompts are written with putStr (no newline), so disable line buffering
  -- to make them appear before the program waits for input.
  hSetBuffering stdout NoBuffering
  mainLoop