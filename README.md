# Daily AI & Salesforce newsletter for Teams: setup guide

This project builds and posts the newsletter by itself every weekday. Nobody approves posts.
Follow the steps in order. Each step says how to know it worked.

How it runs: a timer on GitHub starts the program every weekday morning. The program reads
approved news feeds, asks the AI to pick one AI story and one Salesforce story, writes a locked
fact list from each article, writes the fun post from those facts only, checks it automatically,
and sends it to your Teams channel. If any check fails it posts a pre-written backup post instead.

What you need before you start
- A Microsoft Teams account that can use the Workflows app (ask IT if it is missing).
- A GitHub account (a private repository is recommended).
- An API key for the AI service (step 3).
- About 90 minutes for the first setup.

---

## Step 1. Get your IT checks done (can run in parallel with the other steps)

Ask IT to confirm:
1. The Workflows app is allowed in Teams for you.
2. Using an external AI service is approved. Only public news articles are sent to it. No customer or company data is.
3. Using GitHub (or another scheduler) for a daily job is approved.

## Step 2. Create the Teams webhook link

A. The newsletter link
1. In Teams, open your POC channel. Click the three dots (More options) next to the channel name, then Workflows.
2. Search for the template called "Send webhook alerts to a channel" and open it.
3. Give it a name, such as "Newsletter poster". Confirm the sign-in if asked.
4. Choose your team and the POC channel, then Save.
5. On the page that follows, click "Copy webhook link". Keep this link secret: anyone who has it can post in your channel.

B. A co-owner (important)
A Workflow belongs to one person. If that person leaves the company, it can stop. Open the workflow in
Power Automate (make.powerautomate.com), open its details page, and add a co-owner. The exact wording of
the buttons may differ slightly.

C. Optional: an alert link for yourself
Repeat A, but choose the template "Send webhook alerts to a chat" so failure alerts come to you privately.
Copy that link as well.

## Step 3. Get an AI key

The code uses the Anthropic API. In the Anthropic Console, create an API key and copy it. Check the
current pricing on the Console. The job makes roughly 6 to 12 AI calls a day.
To use a different AI provider, only the file `newsletter/llm.py` needs changing.

## Step 4. Test everything on your own computer first (recommended)

You need Python 3.9 or newer. Nothing else has to be installed. On Windows, also run `pip install tzdata` once.

1. Unzip the project and open a terminal in that folder.
2. Copy `.env.example` to a new file named `.env`. Paste your three values into it.
3. Run the offline tests (no internet needed): `python3 -m unittest discover -s tests`. All should say OK.
4. Run `python3 -m newsletter check-llm`. Expected: it prints the model name and "OK".
5. Run `python3 -m newsletter test-webhook`. Expected: a test message appears in your Teams channel.
   Then run `python3 -m newsletter test-webhook --card` to see how a card looks.
   If nothing appears, open the Workflows app > your workflow > Run history to see why.
6. Run `python3 -m newsletter check-sources`. This tests every news feed.

## Step 5. Fix the news sources

Several feed addresses in `sources.json` are marked "URL not confirmed". `check-sources` shows which work.
- For a feed that fails, open the website, look for an RSS or Atom link, and paste the correct address into `sources.json`.
- If you cannot fix one, set `"enabled": false` for it.
- You need at least two working feeds for AI and two for Salesforce, so a quiet day never leaves you without a story.
- Only list sites you trust. The AI never reads anywhere else.

## Step 6. Do a dry run

Run `python3 -m newsletter run --dry-run --force`.
It builds a real post from real news but sends nothing and saves nothing. Read the output:
- Check it names real stories with the right links.
- Check the tone. To change the voice, edit `prompts/style_guide.md`. To change weekday themes, edit `config.json`.
- Test other days: `--weekday 4` shows a Friday quiz post.
It is normal for some days to use a backup post. That means the safety checks did their job.

## Step 7. Put the project on GitHub

1. Create a new private repository on GitHub.
2. Upload this whole folder (the hidden `.github` folder must go too). With git installed:
   `git init`, `git add .`, `git commit -m "Newsletter bot"`, `git branch -M main`,
   `git remote add origin <your repository address>`, `git push -u origin main`.
   The `.env` file is ignored on purpose. Never upload it.
3. In the repository go to Settings > Secrets and variables > Actions > New repository secret.
   Add three secrets with exactly these names: `ANTHROPIC_API_KEY`, `TEAMS_WEBHOOK_URL`, and (optional) `TEAMS_ALERT_WEBHOOK_URL`.
4. Go to Settings > Actions > General > Workflow permissions and choose "Read and write permissions".
   The daily job needs this to save its history.

## Step 8. Run it once on GitHub

1. Open the Actions tab. If GitHub asks you to enable workflows, do so.
2. Choose "Daily newsletter" > "Run workflow". Keep "Dry run" ticked. Expected: a green tick, and the log shows the post.
3. Run it again with "Dry run" unticked and "Force" ticked. Expected: a real post appears in the POC channel, and a new commit named "Newsletter state ..." appears in the repository.

## Step 9. The schedule is now live

The file `.github/workflows/newsletter.yml` starts the job Monday to Friday at 03:50 UTC, which is 09:20 AM India time.
Two later runs act as a safety net and do nothing if today's post is already out. GitHub can start scheduled
runs late at busy times, so the post may land some minutes after 09:20.
To change the time, edit the `cron` lines. The times are in UTC.

## Daily and weekly routine during the POC (about 5 minutes a day)

- Each morning: look at the channel. Open the Actions tab and check for a green tick.
- Each day's record is in `state/runs/<date>.json`: the stories seen, the fact lists, the drafts, and the reason for each rejection.
- Every Friday: open the week's posts next to their source links and compare. Write down any error. This is your accuracy score for the decision meeting.
- Skip a holiday: add the date (like "2026-12-25") to `skip_dates` in `config.json`.

## When something goes wrong

| What you see | Likely reason | What to do |
| --- | --- | --- |
| No post and no alert | The schedule did not run | Actions tab: check the workflow is enabled. GitHub can pause scheduled workflows in repositories with no activity for a while. |
| Alert says "backup post was used" | No story passed the checks, or feeds were down | Open that day's run file in `state/runs`. Look at "problems" and "feed_errors". |
| Test message sends but nothing in Teams | The Workflow is off, or its owner's sign-in expired | Workflows app > Run history; turn it on or sign in again. |
| `HTTP 401` from the AI | Wrong or expired key | Replace the `ANTHROPIC_API_KEY` secret. |
| Push fails with 403 in the job | Workflow permissions | Step 7, part 4. |
| Too many backup posts | Checks reject drafts, or feeds are thin | Read the "problems" in the run file. Add feeds. Soften wording rules in `prompts/style_guide.md`. Never remove the number checks. |
| Post is too long or too silly | Voice | Edit `prompts/style_guide.md`. Re-run a dry run. |

## What each file does

- `config.json`: name, timezone, weekday themes, limits.
- `sources.json`: the approved news feeds.
- `backup_posts.json`: pre-written posts used when no story passes the checks. Add more any time.
- `prompts/`: the instructions given to the AI (picking, fact lists, writing, fact-checking, voice).
- `newsletter/`: the program. `checks.py` holds the automatic safety checks.
- `state/`: history of what was posted. The job saves it back to GitHub every day.
- `tests/`: offline tests. Run them after you change anything.

## What the automatic checks do

1. Every fact on the fact list must come with a quote that really appears in the article.
2. Every number, quote and link in the post must come from the fact list. Links are added by the program, never by the AI.
3. A second AI pass compares each sentence with the facts and fails the post if anything is added or exaggerated.
4. If the post fails, the AI gets one chance to fix it. After that the next best story is tried. After that, a backup post is used.

These checks make wrong facts unlikely. They cannot make them impossible, which is why the weekly comparison above matters.

## Known limits (good to tell your team)

- Teams Workflows cannot notify the whole channel automatically. Members can turn on channel notifications, or you can try a Teams tag people can join.
- The post comes from the Workflows bot or the workflow owner. The sender name and icon cannot be changed.
- Counting reactions automatically needs extra Microsoft permissions. For the POC, count them by looking at the channel.
- The code keeps the last 90 days of history.
