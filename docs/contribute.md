
# How to contribute to the project

Contributions are highly welcomed! 

??? questions "I have PyLadies/R-Ladies content (blog, YouTube channel, ...), how do I contribute it to the bot?"

    - [Awesome PyLadies' Repository](https://github.com/cosimameyer/awesome-pyladies-blogs)
    - [Awesome R-Ladies' Repository](https://github.com/rladies/awesome-rladies-blogs)

??? questions "I have an idea how to improve the code - how can I share it?"

    Amazing, I'm so happy that you took your time to go through the code and want to make it better!

    - If you have an idea (but no solution yet), feel free to [open an issue](https://github.com/cosimameyer/community-bots/issues/new/choose) or reach out to [Cosima](https://linktr.ee/cosima_meyer).
    - If you have an idea and a solution - amazing! Let's work together with PRs 😊

??? questions "How to collaborate on a code level?"

    To  allow dependency management, this repository uses [`pdm`](https://pdm-project.org/en/latest/) and [`pre-commit`](https://pre-commit.com/) hooks. To get started, there's not a lot you have to do. Just follow these steps:

    1. Install `pdm`. [Here](https://pdm-project.org/en/latest/#installation) are options how to do it.
    2. Now you're good to go. `pyproject.toml` contains all relevant info. You just need to run `pdm install` in you terminal. This will create a `.venv/` folder with the Python packages installed in.
    3. If you want to add a package, don't do it manually. Run `pdm add <package_name>`.
    4. This repository also relies on pre-commit hooks. To have them activated on your end, make sure to run `pdm run pre-commit install`. They'll be running in the background and just complain if something's not right. Otherwise, you'll not really see them 😊

    In case you run into issues here, let me know! We'll figure it out 😊

??? questions "What's the default branch?"

    The default branch is main. To contribute to it, create a feature branch and open a PR with your changes. Direct pushes to `main` are blocked (because that's where our production code is) but collaboration is of course highly welcome 😊


??? questions "Any other open questions?"

    If you have any questions or suggestions, please reach out to
    [Cosima](https://linktr.ee/cosima_meyer) or open an
    [issue](https://github.com/cosimameyer/community-bots/issues/new/choose).