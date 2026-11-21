# Claude plugins by marank

A [plugin marketplace](https://docs.claude.com/en/docs/claude-code/plugin-marketplaces) for Claude.

| Plugin | What it does |
|---|---|
| [django-spa-defaults](plugins/django-spa-defaults) | Scaffolds a Django project with a Vue or React SPA using one set of house defaults, or checks an existing repo against them and brings it in line. |
| [setup-github-repo](plugins/setup-github-repo) | Sets a GitHub repository's settings (merging, rulesets, security, Actions, releases) to one set of defaults with `gh`, idempotent with a dry run. |

## Install

In Claude Code:

```
/plugin marketplace add marank/claude-plugins
/plugin install django-spa-defaults@marank-plugins
/plugin install setup-github-repo@marank-plugins
```

In the Claude apps, a skill can also be added on its own: zip its folder under `plugins/<plugin>/skills/` and upload it as a custom skill.

## License

MIT, see [LICENSE](LICENSE). Projects generated with these plugins choose their own license.
