You are checking a draft newsletter post against the facts it was meant to be based on.

FACT SHEETS (the only allowed source of facts):
{{FACTS}}

EARLIER FACTS (only these may be used for quiz questions):
{{POOL}}

DRAFT TO CHECK:
{{DRAFT}}

Go through every sentence in the draft's headline, stories, why_it_matters, jargon and quiz. Each sentence must be one of:
- supported by a fact above, or
- harmless wording that makes no factual claim (a greeting, humour, a question, or a clearly labelled comparison such as "Think of it like ...").

FAIL the draft if ANY sentence does one of these:
- adds a fact that is not in the fact sheets;
- changes a number, date, name or availability (for example turns a beta, plan or preview into something available now);
- exaggerates or ranks ("first", "biggest", "revolutionary", "will transform") when the facts do not say it;
- states a cause, result or prediction that is not in the facts;
- puts a claim from one story into another story;
- has a quiz answer that is not supported by the facts, or a quiz question with more than one defensible answer.

The jargon explanation may use a general, correct definition of the term. It must not make claims about specific products, dates, numbers or availability.

Be strict. When unsure, fail it.

Reply with JSON only:
{"verdict": "pass", "problems": []}
or
{"verdict": "fail", "problems": ["short description of each problem, quoting the bad words"]}
