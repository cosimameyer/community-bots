# PyLadies and R-Ladies Bots

> These bots are still WIP and the current version presents a MVP.

## What this repository is about

This project focuses on building community-driven bots for Bluesky and Mastodon to support and grow the Python, R, and data community. The bots help by boosting posts tagged with #pyladies or #rladies, sharing data visualizations, posting useful resources, and celebrating community achievements. Designed to increase engagement and visibility, the bots run automatically using Mastodon’s API and open-source tools. The project also provides a detailed, open guide for others interested in setting up similar bots. At its core, it’s about using automation to strengthen and connect our communities.

This projects marries multiple components:

- Sharing content by PyLadies and R-Ladies
- Sharing Amazing Women in Tech

Here are more posts about the project:
- [Blog Post: Awesome PyLadies' Repository](https://cosimameyer.com/post/2023-04-25-building-mastodon-bots-and-promoting-the-community/)
- [Blog Post: Building Mastodon Bots](https://cosimameyer.com/post/2023-09-17-building-mastodon-bots-and-promoting-the-community-part-2/)
- [Blog Post: How to add Gemini to your Python project](https://cosimameyer.com/post/how-to-add-google-gemini-to-your-python-project-that-makes-use-of-github-actions/)

### Where can I find the live bots?

The bots are currently live on Mastodon an Bluesky. I'd love to extend it to other platforms - so if you have ideas, let me know!

#### Bluesky 

- [PyLadies Bot](https://bsky.app/profile/did:plc:cyhjdt4mp7h4c2ufw3nwcqqx)
- [R-Ladies Bot]()

#### Mastodon

- [PyLadies Bot](https://botsin.space/@pyladies_bot)
- [R-Ladies Bot]()

### I have PyLadies/R-Ladies content (blog, YouTube channel, ...), how do I contribute it to the bot?

- [Awesome PyLadies' Repository](https://github.com/cosimameyer/awesome-pyladies-blogs)
- [Awesome R-Ladies' Repository](https://github.com/rladies/awesome-rladies-blogs)

## How to contribute to the project

Contributions are highly welcomed! 

- If you have an idea (but no solution yet), feel free to [open an issue](https://github.com/cosimameyer/community-bots/issues/new/choose) or reach out to [Cosima](https://linktr.ee/cosima_meyer).
- If you have an idea and a solution - amazing! Let's work together with PRs 😊

### `pdm`
To  allow dependency management, this repository uses [`pdm`](https://pdm-project.org/en/latest/) and [`pre-commit`](https://pre-commit.com/) hooks. To get started, there's not a lot you have to do. Just follow these steps:

1. Install `pdm`. [Here](https://pdm-project.org/en/latest/#installation) are options how to do it.
2. Now you're good to go. `pyproject.toml` contains all relevant info. You just need to run `pdm install` in you terminal. This will create a `.venv/` folder with the Python packages installed in.
3. If you want to add a package, don't do it manually. Run `pdm add <package_name>`.
4. This repository also relies on pre-commit hooks. To have them activated on your end, make sure to run `pdm run pre-commit install`. They'll be running in the background and just complain if something's not right. Otherwise, you'll not really see them 😊

In case you run into issues here, let me know! We'll figure it out 😊

### What's the default branch?

The default branch is main. To contribute to it, create a feature branch and open a PR with your changes. Direct pushes to `main` are blocked (because that's where our production code is) but collaboration is of course highly welcome 😊

## Any Open Questions?

If you have any questions or suggestions, please reach out to
[Cosima](https://linktr.ee/cosima_meyer) or open an
[issue](https://github.com/cosimameyer/community-bots/issues/new/choose).

## License

[![CC0](https://upload.wikimedia.org/wikipedia/commons/6/69/CC0_button.svg)](https://creativecommons.org/publicdomain/zero/1.0/)