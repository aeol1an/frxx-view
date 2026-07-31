"""Shell commands that operate on radar moments."""

from frxxv.shell.moments import dealias, doppler, nav, savefig, vals, write


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

    if command.name in ("begin", "end", "n", "ls", "le"):
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

    if command.name == "coords":
        vals.execute_coords(
            app_state,
            interaction_manager,
            shell_output,
            *command.args,
        )
        return True

    if command.name == "raytime":
        vals.execute_raytime(
            app_state,
            interaction_manager,
            shell_output,
            *command.args,
        )
        return True

    if command.name == "center":
        vals.execute_center(
            app_state,
            interaction_manager,
            shell_output,
            *command.args,
        )
        return True

    if command.name in doppler.COMMANDS:
        doppler.execute(
            app_state,
            interaction_manager,
            shell_output,
            command.name,
            *command.args,
        )
        return True

    if command.name in dealias.COMMANDS:
        dealias.execute(
            app_state,
            interaction_manager,
            shell_output,
            command.name,
            *command.args,
        )
        return True

    if command.name in write.COMMANDS:
        write.execute(
            app_state,
            interaction_manager,
            shell_output,
            command.name,
            *command.args,
        )
        return True

    if command.name == "savefig":
        savefig.execute(
            app_state,
            interaction_manager,
            shell_output,
            *command.args,
        )
        return True

    return False
