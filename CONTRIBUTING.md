# Contributing

Thanks for helping with Kaldr Studio. Bug reports, fixes and small improvements are welcome. For a large change, open an issue first so we can agree on the approach before you spend time on it.

## Before you open a pull request

- Keep each pull request to one change.
- Run the checks CI runs. For Python, install `requirements-dev.txt`, then run `ruff check .` and `pytest` from the repository folder. For the web, run `npm run lint` and `npm run build` in `web/`.
- Check the change in the running studio.
- Don't commit art, audio, model weights, API keys or anything under `private/`.
- Only submit work you wrote yourself, or work whose license lets you contribute it under the terms below.

## Contributor License Agreement

Kaldr Studio is source-available under FSL-1.1-ALv2. Kaldr Industries LLC also runs Kaldr Studio Cloud and may offer the software under other licenses. To keep that possible, every contribution is made under this agreement. Opening a pull request means you agree to it.

1. **Definitions.** "We" and "us" means Kaldr Industries LLC. "You" means the person submitting a contribution, or the organization they submit it for. A "Contribution" is any code, documentation or other material you submit to this project, in a pull request, patch, issue or any other way.

2. **Copyright license.** You grant us and anyone who receives software from us a perpetual, worldwide, non-exclusive, no-charge, royalty-free, irrevocable license to reproduce, prepare derivative works of, publicly display, publicly perform, sublicense and distribute your Contributions and derivative works of them, under any license, including proprietary and commercial ones.

3. **Patent license.** You grant us and anyone who receives software from us a perpetual, worldwide, non-exclusive, no-charge, royalty-free, irrevocable patent license to make, have made, use, offer to sell, sell, import and otherwise transfer your Contributions, for any patent claims you can license that your Contribution alone, or combined with this project, would infringe.

4. **You keep your copyright.** This agreement is a license, not a transfer. You can still use your own Contributions however you like.

5. **Your promises.** You confirm that:
   - each Contribution is your original work, or you have the right to submit it under this agreement;
   - if your employer or anyone else has rights in your Contribution, they have allowed you to submit it under this agreement, or have waived those rights;
   - you will tell us if you learn that any of this stops being true.

6. **No obligation.** We don't have to use your Contribution. If we do, we don't have to credit you beyond what the project's history records.

7. **No warranty.** Apart from the promises in section 5, you provide your Contributions "as is", without warranties of any kind.

Third-party code you include must be under a license compatible with this agreement, such as MIT, BSD or Apache-2.0. Say in the pull request where it came from.
