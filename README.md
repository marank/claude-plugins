# Claude plugins by marank

A [plugin marketplace](https://docs.claude.com/en/docs/claude-code/plugin-marketplaces) for Claude.

| Plugin | What it does |
|---|---|
| [django-spa-defaults](plugins/django-spa-defaults) | Scaffolds a Django project with a Vue or React SPA using one set of house defaults, or checks an existing repo against them and brings it in line. |

## Install

In Claude Code:

```
/plugin marketplace add marank/claude-plugins
/plugin install django-spa-defaults@marank-plugins
```

In the Claude apps, a skill can also be added on its own: zip the folder `plugins/django-spa-defaults/skills/django-spa-defaults` and upload it as a custom skill.

## License

MIT, see [LICENSE](LICENSE). Projects generated with these plugins choose their own license.
