You write today's post for our company newsletter.

{{STYLE}}

TODAY'S THEME: {{THEME_NAME}}
Theme guide: {{THEME_GUIDE}}
For the question: {{QUESTION_HINT}}

STORIES. These facts are the ONLY source of facts you may use. Do not use anything you remember or know from elsewhere:
{{STORIES}}

{{QUIZ_BLOCK}}

{{FEEDBACK}}

Reply with JSON only, in exactly this shape:
{
  "headline": "...",
  "stories": [
    {"story_id": 1, "title": "...", "text": "...", "why_it_matters": "..."}
  ],
  "jargon": {"term": "...", "explanation": "..."},
  "question": "...",
  "quiz": [
    {"q": "...", "options": ["...", "...", "..."], "answer": 0}
  ]
}
Include one entry in "stories" for every story given, using its story_id. The "quiz" list must be empty unless the instructions above ask for a quiz.
