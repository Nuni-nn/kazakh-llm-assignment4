# Frozen Annotation Guideline — Assignment 4

## 1. Primary-error counting rule
Each distinct error span receives exactly one primary category:
- Grammatical
- Morphological
- Lexical

A supplementary label may be attached to the same span, but it does not add another primary error. Therefore one span cannot increase the primary linguistic error count by more than 1.

## 2. Primary categories
### Grammatical
Sentence-level grammatical structure or grammatical relations, including syntactic agreement or construction errors.

### Morphological
Incorrect word form or affix, including case, number, possession, person, tense/mood, derivational or inflectional morphology.

### Lexical
Incorrect or clearly unnatural word choice, collocation, lexical meaning, or lexicalised calque.

## 3. Overlap rules
- A vowel-harmony/singarmonism suffix error is Primary = Morphological; Supplementary = Singarmonism.
- A calque caused mainly by word choice/collocation is Primary = Lexical; Supplementary = Calque.
- A calque caused mainly by sentence structure is Primary = Grammatical; Supplementary = Calque.
- Orthographic/script, code-switching, factual, instruction/format and other supplementary issues are not added to the primary count unless there is also a separate primary linguistic error.
- If an annotator is uncertain between two primary categories, record the candidate span, both considered categories in Notes, and send it to adjudication. Do not double-count it.

## 4. Human validation and judge-miss assessment
All judge-flagged primary-error candidates are manually verified.

A fixed stratified sample of 150 complete responses is independently annotated from scratch by a second annotator. The sample is balanced as closely as possible across tested models, runs, and task groups.

For judge false-negative assessment, the independently annotated sample is treated as the human reference. Judge recall is calculated at the adjudicated primary-error-span level:
recall = matched human primary-error spans / all human primary-error spans.

If overall judge recall is below 0.90, an additional stratified sample of 150 complete responses is independently annotated from scratch. The observed miss rate is reported in Results and Threats to Validity.

## 5. Cohen's kappa unit
For Cohen's kappa, the comparison unit is the response-category pair. For each response, each primary category is coded as Present or Absent. Kappa is reported separately for Grammatical, Morphological and Lexical categories. Raw percentage agreement is also reported.

## 6. Adjudication
Disagreements are resolved using this frozen guideline. Original annotations are never overwritten; adjudicated labels are stored separately.
