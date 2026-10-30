# Security Policy

## Reporting a problem

Please don't report security problems in public issues. Use GitHub's private reporting instead: open the **Security** tab of this repository and choose **Report a vulnerability**.

Tell us what the problem is, which version or commit it affects, and the steps to reproduce it. We'll confirm we've received it, keep you updated while we fix it, and credit you in the release notes if you'd like.

## What's in scope

- The local server in `app/`, including file handling, job IDs and anything that could let a web page or another user on the machine reach it.
- Handling of the OpenRouter API key.
- The web interface in `web/`.

Problems in third-party packages, models or services should go to their own maintainers. Tell us too if Kaldr Studio's use of them makes the problem worse.

## Running it safely

- The server listens on `127.0.0.1` only. Don't expose it to a network without putting your own authentication in front of it.
- Use an OpenRouter key made just for Kaldr Studio, with a spending limit.
- Keep Python packages, especially `yt-dlp`, up to date.
