"""System checks: UUID primary keys on our own models, and a sane TRUSTED_PROXIES."""

import ipaddress

from django.apps import apps
from django.core import checks
from django.db import models

from config.env import env_list


@checks.register(checks.Tags.models)
def uuid_primary_keys(app_configs=None, **kwargs):
    errors = []
    configs = app_configs or apps.get_app_configs()
    for config in configs:
        if not config.name.startswith("apps."):
            continue
        for model in config.get_models():
            if model._meta.proxy or not model._meta.managed:
                continue
            if not isinstance(model._meta.pk, models.UUIDField):
                errors.append(
                    checks.Error(
                        f"{model._meta.label} must use a UUID primary key.",
                        hint="Inherit from apps.core.models.UUIDModel (or TimeStampedModel).",
                        obj=model,
                        id="core.E001",
                    )
                )
    return errors


def trusted_proxy_problems(entries: list[str]) -> list[str]:
    """What is wrong with a TRUSTED_PROXIES value (empty list: nothing).

    Each entry is an IP address or a CIDR range. `none` (alone) says on purpose that no proxy
    is in front. A range that covers every address is refused: nginx would then believe any
    client's X-Forwarded-For, and rate limits and logs could be dodged by lying about the address.
    """
    if entries == ["none"]:
        return []
    problems = []
    for entry in entries:
        try:
            network = ipaddress.ip_network(entry, strict=False)
        except ValueError:
            problems.append(f"{entry!r} is not an IP address or CIDR range")
            continue
        if network.prefixlen == 0:
            problems.append(f"{entry!r} trusts every address")
    return problems


@checks.register()
def trusted_proxies(app_configs=None, **kwargs):
    return [
        checks.Error(
            f"TRUSTED_PROXIES: {problem}.",
            hint="List the address(es) of your TLS proxy, or leave it empty (or set `none`).",
            id="core.E002",
        )
        for problem in trusted_proxy_problems(env_list("TRUSTED_PROXIES"))
    ]
