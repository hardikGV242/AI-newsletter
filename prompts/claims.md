You are checking a draft newsletter post against the facts it was meant to be based on.

FACT SHEETS (the only allowed source of facts):
{{FACTS}}

EARLIER FACTS (only these may be used for quiz questions):
{{POOL}}

DRAFT TO CHECK:
{{DRAFT}}

Go through every sentence in the draft's headline, stories (tag, title, text, why_it_matters) and quiz. Each sentence must be one of:
- supported by a fact above, or
- harmless wording that makes no factual claim (a question, or a clearly labelled comparison such as "Think of it like ..."), or
- in why_it_matters only: a recommendation to the consulting team about what to review, plan, test or tell clients (for example "Review client orgs that use X before the change"). Advice is allowed; any statement inside it about what a product does, costs or when it ships must still be supported by the facts.

FAIL the draft if ANY sentence does one of these:
- adds a fact that is not in the fact sheets;
- writes a number in words instead of digits (for example "fifty-five percent" instead of "55%");
- changes a number, date, name or availability (for example turns a beta, plan or preview into something available now);
- exaggerates or ranks ("first", "biggest", "revolutionary", "will transform") when the facts do not say it;
- states a cause, result or prediction that is not in the facts;
- puts a claim from one story into another story;
- has a quiz answer that is not supported by the facts, or a quiz question with more than one defensible answer.


Be strict. When unsure, fail it.

Reply with JSON only:
{"verdict": "pass", "problems": []}
or
{"verdict": "fail", "problems": ["short description of each problem, quoting the bad words"]}
