"""Shell commands that operate on radar moments."""

from frxxv.shell.moments import nav, vals


def execute(app_state, interaction_manager, shell_output, command) -> bool:
    """Dispatch a parsed command belonging to a moments data window."""
    if command.name in ("+", "-"):
        direction = 1 if command.name == "+" else -1
        nav.execute(
            app_state,
            interaction_manager,
            shell_output,
            direction,
            *command.args,
        )
        return True

    if command.name in ("begin", "end", "n", "ls"):
        nav.execute(
            app_state,
            interaction_manager,
            shell_output,
            command.name,
            *command.args,
        )
        return True

    if command.name == "vals":
        vals.execute(
            app_state,
            interaction_manager,
            shell_output,
            *command.args,
        )
        return True

    return False
