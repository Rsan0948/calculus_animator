# Curriculum Fill Playbook

This playbook shows how to convert your long-form curriculum (`curriculum.txt`) into app-ready content fast and consistently.

## What You Already Have

- High-quality scope and sequencing in `curriculum.txt`
- Runtime schema support in:
  - `data/curriculum.json`
  - `data/glossary.json`
- Template pack in:
  - `templates/curriculum_content_template.json`
  - `templates/curriculum_seed_from_curriculum_txt.json`
  - `templates/slide_types_reference.json`
  - `templates/glossary_template.json`

## Recommended Fill Strategy

1. Start from `templates/curriculum_seed_from_curriculum_txt.json`.
2. Copy it into `data/curriculum.json` when you are ready to replace the starter data.
3. Fill one chapter at a time; do not try to fill the full curriculum in one pass.
4. For each chapter:
   - Add all `slides`
   - Fill `midpoint_quiz.questions`
   - Fill `final_test.questions`
5. Add glossary terms in parallel as you add slides.
6. Keep `required_to_take = true` and `required_to_pass = false` for midpoint quiz.
7. Keep `optional_recommended = true` for chapter tests unless you intentionally change policy.

## How to Map Your Current Curriculum Text

Your text is already organized by pathway and topic clusters. Use this mapping:

- **Pre-Calc**
  - Functions and Graphs
  - Exponential and Logarithmic Functions
  - Trigonometry
  - Complex Numbers
  - Sequences and Series (Intro)
  - Conic Sections and Analytic Geometry
  - Vectors and Parametric Equations
  - Introductory Limits
- **Calc I**
  - Limits and Continuity
  - Derivatives and Applications
  - Integrals and FTC
- **Calc II**
  - Advanced Integration Techniques
  - Applications of Integration
  - Parametric and Polar
  - Sequences and Series
- **Advanced Calculus**
  - Multivariable Functions + Partial Derivatives
  - Double/Triple Integrals
  - Vector Calculus + Green/Stokes/Divergence

This mapping is pre-seeded in `templates/curriculum_seed_from_curriculum_txt.json`.

## Chapter Fill Rules (Best Results)

For each chapter:

1. **Slide count target**
   - Short chapter: 8-12 slides
   - Medium chapter: 12-18 slides
   - Long chapter: 18-30 slides

2. **Slide composition target**
   - 60% `lesson`
   - 25% `worked_example`
   - 10% `summary`
   - 5% `practice`

3. **Micro quiz policy**
   - Keep `micro_quiz_interval`:
     - 4 for dense chapters
     - 5 for normal chapters
     - 6 for lighter chapters

4. **Midpoint quiz**
   - At least 5 questions
   - Required to take, not required to pass
   - Include explanation per question

5. **Final test (optional but recommended)**
   - At least 8 questions
   - Include mixed difficulty
   - Include explanation per question

## Slide Authoring Pattern

For each `lesson` slide:
- 1-2 `text` blocks
- 1 `example` block
- 1-3 glossary terms in `glossary_terms`
- at least one `related_topic_id` when available

For each `worked_example` slide:
- `problem` block first
- 2-5 `step` blocks
- include the governing rule name in one step

## Glossary Growth Workflow

As you add content:

1. Add any new term to `data/glossary.json` if:
   - it appears 2+ times, or
   - it is foundational (e.g. limit, derivative, convergence)
2. Add aliases for plural/synonym forms.
3. Link term to:
   - `related_topic_ids`
   - `related_formula_ids` when relevant

This maximizes automatic inline linking across the app.

## Quality Checklist Before Each Commit

- Every chapter has:
  - non-empty `slides`
  - non-empty `midpoint_quiz.questions`
  - non-empty `final_test.questions` (recommended)
- Every slide has:
  - unique `id`
  - `type`, `title`
  - at least one `content_block`
- Every quiz/test question has:
  - prompt
  - answer key field (`correct_choice_index` or `expected_answer`)
  - explanation
- All `related_topic_ids` exist in learning library
- All glossary terms referenced by slides exist in `data/glossary.json`

## Fast Fill Pipeline (for your other AI)

Use this sequence:

1. Fill chapter outlines only (titles, descriptions, ids).
2. Fill slide skeletons (type/title/blocks with short placeholders).
3. Expand slide block content with beginner-friendly explanations.
4. Generate midpoint quizzes and final tests.
5. Generate/merge glossary terms and aliases.
6. Run validation pass for IDs and cross-links.

This two-stage fill (structure then prose) produces fewer schema errors and better consistency.
