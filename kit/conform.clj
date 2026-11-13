(ns conform
  "Runs every example case against your program and says what fails.

  A case is one JSON file in cases/:
    {\"name\": \"03-...\", \"why\": \"...\", \"rules\": [\"R2\"], \"input\": {...}, \"expect\": {...}}

  For each case your program gets ONE JSON document on stdin,
    {\"input\": <the case's input>, \"policy\": <policy.json, or {} if there is none>}
  and writes ONE JSON document to stdout (logs go to stderr). The answer is then
  compared with \"expect\":
    - objects: every key in \"expect\" must be in the answer with an equal value;
      keys the case leaves out are not checked (inside lists too);
    - lists: same length, equal item by item, in order;
    - numbers by value, so 2 equals 2.0; everything else must be identical.

  Exit code 0: every case passed. 1: a case failed or could not run.
  2: no cases were found, or a file could not be read."
  (:require [babashka.fs :as fs]
            [babashka.process :as p]
            [cheshire.core :as json]
            [clojure.string :as str]))

(defn compare-json
  "Differences between an answer and an expectation, as [path got want] triples."
  ([got want] (compare-json got want "$"))
  ([got want path]
   (cond
     (map? want)
     (if-not (map? got)
       [[path got want]]
       (into [] (mapcat (fn [[k v]]
                          (if (contains? got k)
                            (compare-json (get got k) v (str path "." k))
                            [[(str path "." k) ::missing v]])))
             want))

     (sequential? want)
     (if-not (and (sequential? got) (= (count got) (count want)))
       [[path got want]]
       (into [] (mapcat (fn [i g w] (compare-json g w (str path "[" i "]")))
                        (range) got want)))

     (and (number? got) (number? want))
     (if (== got want) [] [[path got want]])

     :else
     (if (= got want) [] [[path got want]]))))

(defn- brief [v]
  (let [s (if (= v ::missing) "<missing>" (json/generate-string v))]
    (if (> (count s) 80) (str (subs s 0 79) "…") s)))

(defn- run-case
  "[answer nil] or [nil problem]."
  [cmd kase policy timeout-ms]
  (let [request (json/generate-string {"input" (get kase "input") "policy" policy})
        proc    (p/process {:in request :out :string :err :string} cmd)
        result  (deref proc timeout-ms ::timeout)]
    (if (= result ::timeout)
      (do (p/destroy-tree proc)
          [nil (str "no answer within " (/ timeout-ms 1000.0) " s")])
      (let [{:keys [exit out err]} result]
        (if-not (zero? exit)
          [nil (str "exit code " exit ": " (or (last (str/split-lines (str/trim err))) "(no stderr)"))]
          (try [(json/parse-string out) nil]
               (catch Exception _ [nil "stdout is not one JSON document"])))))))

(defn- parse-args [args]
  (loop [[a b & more :as all] args
         opts {:cmd "bb run" :cases "cases" :policy "policy.json" :timeout 30 :only nil}]
    (cond
      (empty? all) opts
      (= a "--cmd") (recur more (assoc opts :cmd b))
      (= a "--cases") (recur more (assoc opts :cases b))
      (= a "--policy") (recur more (assoc opts :policy b))
      (= a "--only") (recur more (assoc opts :only b))
      (= a "--timeout") (recur more (assoc opts :timeout (parse-double b)))
      :else (do (println (str "conform: unknown argument " a "; see bb help")) ::bad-args))))

(defn main
  "Runs the cases; returns the exit code."
  [args]
  (let [{:keys [cmd cases policy timeout only] :as opts} (parse-args args)]
    (if (= opts ::bad-args)
      2
      (let [policy-doc (if (fs/exists? policy)
                         (try (json/parse-string (slurp policy)) (catch Exception e e))
                         (do (println (str "note: no " policy " found, so every case gets the policy {}")) {}))
            files      (->> (fs/glob cases "*.json")
                            (map str)
                            sort
                            (filter #(or (nil? only) (str/starts-with? (fs/file-name %) only))))]
        (cond
          (instance? Exception policy-doc)
          (do (println (str "conform: cannot read " policy ": " (ex-message policy-doc))) 2)

          (empty? files)
          (do (println (str "conform: no case files in " cases "/")) 2)

          :else
          (let [tally (reduce
                        (fn [tally path]
                          (let [label (str/replace (fs/file-name path) #"\.json$" "")
                                kase  (try (json/parse-string (slurp path)) (catch Exception _ ::unreadable))]
                            (cond
                              (= kase ::unreadable)
                              (do (println (str "ERROR " label ": cannot read the case")) (update tally :errors inc))

                              (not (contains? kase "expect"))
                              (do (println (str "ERROR " label ": the case has no \"expect\"")) (update tally :errors inc))

                              :else
                              (let [[got problem] (run-case cmd kase policy-doc (long (* 1000 timeout)))]
                                (if problem
                                  (do (println (str "ERROR " label ": " problem)) (update tally :errors inc))
                                  (let [diffs (compare-json got (get kase "expect"))]
                                    (if (seq diffs)
                                      (let [[where g w] (first diffs)
                                            more (when (next diffs) (str " (+" (dec (count diffs)) " more)"))]
                                        (println (str "FAIL  " label " " where " got=" (brief g) " want=" (brief w) more))
                                        (update tally :failed inc))
                                      (do (println (str "ok    " label)) (update tally :passed inc)))))))))
                        {:passed 0 :failed 0 :errors 0}
                        files)]
            (println (str "Ran " (count files) " cases: " (:passed tally) " passed, " (:failed tally)
                          " failed, " (:errors tally) " could not run."))
            (if (= (count files) (:passed tally)) 0 1)))))))

(defn help
  "What `bb help` prints."
  []
  (println "Student kit — run these from the root of your repo.

  bb help       this page
  bb run        runs YOUR program: one JSON document on stdin, one on stdout.
                Edit the run task in bb.edn so it starts your program, in any language.
  bb conform    runs every case in cases/ through `bb run` and says what fails.
                Options: --only 03   --timeout 30   --cmd \"python3 run.py\"

A case is one JSON file in cases/:
  {\"name\": \"01-...\", \"why\": \"...\", \"rules\": [\"R1\"], \"input\": {...}, \"expect\": {...}}

Your program gets {\"input\": ..., \"policy\": ...} on stdin, where policy is your policy.json,
and answers with one JSON document. Every key in \"expect\" must be in your answer with an equal
value; keys the case leaves out are not checked. Lists must match in full and in order.
2 equals 2.0. JSON keys are snake_case; times are UTC with a Z.

Exit code 0 means every case passed. Keep it that way in CI."))
