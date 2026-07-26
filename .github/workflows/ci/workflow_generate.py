#!/usr/bin/env python

import shlex
import textwrap

import jinja2
import yaml


class GithubActionsYamlLoader(yaml.SafeLoader):
    @staticmethod
    def _unsupported(kind, token):
        return SyntaxError(
            f"Github Actions does not support {kind}:\n{token.start_mark}"
        )

    def fetch_alias(self):
        super().fetch_alias()
        raise self._unsupported("aliases", self.tokens[0])

    def fetch_anchor(self):
        super().fetch_anchor()
        raise self._unsupported("anchors", self.tokens[0])


environment = jinja2.Environment(
    block_start_string="<%",
    block_end_string="%>",
    variable_start_string="<@",
    variable_end_string="@>",
    comment_start_string="<#",
    comment_end_string="#>",
    lstrip_blocks=True,
    trim_blocks=True,
)

with open(".github/workflows/ci/workflow_context.yml") as fp:
    context = yaml.load(fp, Loader=yaml.SafeLoader)
with open(".github/workflows/ci/workflow_template.yml") as fp:
    template = environment.from_string(fp.read())

for j in context["jobs"]:
    base_type = j["type"].split("_")[0]
    j["id"] = "{}_{}".format(
        base_type,
        j["variant"].lower().replace(" ", "_").replace(".", ""),
    )
    j["name"] = "{} ({})".format(base_type.capitalize(), j["variant"])
    j["needs"] = j.get("needs", [])
    j["reqs"] = [f"reqs/{r}.txt" for r in j["reqs"]]
    j["cache_extra_deps"] = j.get("cache_extra_deps", [])
    if "python" not in j:
        j["python"] = context["default_python"]

    if context["skippy_enabled"]:
        # Path to the "skip_cache" file.
        j["skip_cache_path"] = ".skip_cache_{id}".format(**j)
        # Name of the "skip_cache" (name + tree SHA1 = key).
        j["skip_cache_name"] = "skip_{id}_py-{python}_{platform}".format(
            cache_epoch=context["cache_epoch"], **j
        )
    shell_definition = []
    for k, v in sorted(j.items()):
        if isinstance(v, list):
            v = "(" + " ".join(map(shlex.quote, v)) + ")"
        else:
            v = shlex.quote(v)
        shell_definition.append(f"job_{k}={v}")
    j["shell_definition"] = "; ".join(shell_definition)

# Render template.
workflow = template.render(context)

# Save result.
with open(".github/workflows/ci.yml", "w") as fp:
    fp.write(
        textwrap.dedent(
            """
        #
        # DO NOT MODIFY! AUTO-GENERATED FROM:
        # .github/workflows/ci/workflow_template.yml
        #

        """
        ).lstrip()
    )
    fp.write(workflow)

    # Ensure the generated file ends with a trailing newline.
    fp.write("\n")

# And try parsing it to check it's valid YAML,
# and ensure anchors/aliases are not used.
GithubActionsYamlLoader(workflow).get_single_data()
