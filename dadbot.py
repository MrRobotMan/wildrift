import configparser
import datetime as dt
import itertools
import json
import logging
import random
from collections import defaultdict
from pathlib import Path
from typing import DefaultDict, Optional

import discord
import discord.ext.commands as commands

TIMEOUTS = Path("timeouts.json")
CHAMPS = Path("champs.json")

handler = logging.FileHandler(filename="discord.log", encoding="utf-8", mode="w")


def get_champs() -> tuple[list[str], DefaultDict[str, list[str]]]:
    """
    Read in the data on the champions

    >>> get_champs() # doctest: +ELLIPSIS
    ({'Ahri': ['Mid'], ...}, \
DefaultDict(<class 'list'>, {'Mid': ['Ahri', ...], \
'Baron': ['Akali', ...], ...}))
    """
    with CHAMPS.open() as f:
        champs_data: dict[str, list[str]] = json.load(f)

    champ_positions: DefaultDict[str, list[str]] = defaultdict(list)

    for champ, positions in champs_data.items():
        for pos in positions:
            champ_positions[pos].append(champ)

    return list(champs_data.keys()), champ_positions


def make_team(champ_positions: DefaultDict[str, list[str]]) -> list[str]:
    """
    Get a random team of 5 champs based on where they normally play.

    >>> random.seed(1)
    >>> make_team({'Mid': ['Aurelion Sol', 'Orianna'], \
'Baron': ['Darius', 'Riven'], \
'Support': ['Janna', 'Senna'], \
'Jungle': ['Evelynn', 'Rengar'], \
'Dragon': ['Lucian', 'Jinx']})
    ['Mid Aurelion Sol', 'Baron Darius', 'Support Senna', \
'Jungle Evelynn', 'Dragon Jinx']
    """
    team: list[str] = []
    for position, champs in champ_positions.items():
        champ = random.choice(champs)
        # Uncomment below when AP / AD / Utility stuff is worked out
        # build = random.choice(champs_data[champ]['builds'])
        team.append(f"{position} {champ}")  # Add build once implemented
    return team


def make_chaos(champs: list[str]) -> list[str]:
    """
    Get a fully random ream of 5 champs. They will get randomly assigned
    to AD / AP / Tank as well as positions.

    >>> random.seed(1)
    >>> make_chaos(['Aurelion Sol', 'Darius', 'Janna', 'Evelynn', 'Lucian', \
'Ezreal', 'Blitzcrank', 'Kennen', 'Draven', 'Varus'])
    ['AP Baron Janna', 'AP Dragon Darius', 'Tank Mid Lucian', \
'AP Jungle Aurelion Sol', 'AD Support Evelynn']
    """
    positions = ["Baron", "Dragon", "Mid", "Jungle", "Support"]
    build_opts = ["AD", "AP", "Tank"]
    team = random.sample(champs, 5)
    builds = [random.choice(build_opts) for _ in positions]
    return [f"{builds[i]} {positions[i]} {champ}" for i, champ in enumerate(team)]


def get_user_timeout_data(user: discord.Member) -> tuple[int, int, str]:
    """Checks if the indicated user is in timeout

    Args:
        user (discord.Member): User's name

    Returns:
        tuple[int, int]: Number of times in timeout and duration (seconds)
    """
    with TIMEOUTS.open() as fp:
        data: dict[str, tuple[int, int, str]] = json.load(fp)
    return data.get(user.name, (0, 0, user.name))


def get_timeout_leaderboard() -> Optional[tuple[str, str]]:
    """Return the most timed out people.

    Returns:
        tuple[list[tuple[int, str]]]: users and number of timeouts / total time.
    """
    with TIMEOUTS.open() as fs:
        data: dict[str, tuple[int, int, str]] = json.load(fs)
    if not data:
        return None
    reversed_data = {(v[0], v[1]): v[2] for v in data.values()}
    timed_out_qty = sorted(list(reversed_data.items()), key=lambda x: x[0][0])[:3]
    timed_out_time = sorted(list(reversed_data.items()), key=lambda x: x[0][1])[:3]
    longest_name = max(len(user[2]) for user in data.values())
    most_timed_out = "\n".join(
        f"{user[1]:{longest_name}} | {user[0][0]}" for user in timed_out_qty
    )
    longest_timed_out = "\n".join(
        f"{user[1]:{longest_name}} | {user[0][1]}" for user in timed_out_time
    )
    return (most_timed_out, longest_timed_out)


def main() -> None:
    """
    The main bot. Has commands for team, teams, and chaos.
    """
    config = configparser.ConfigParser()
    config.read("env.ini")
    bot_token = config["DISCORD"]["BOT_TOKEN"]

    champs, champ_positions = get_champs()

    intents = discord.Intents(
        messages=True,
        members=True,
        message_content=True,
    )
    bot = commands.Bot(command_prefix="!", intents=intents)

    @bot.command(name="team", help="Responds with a random team")
    async def on_message(ctx: commands.Context) -> None:
        """
        (1) 5 champ team with roles based on where they normally play
        """
        await ctx.send("\n".join(make_team(champ_positions)))

    @bot.command(name="teams", help="Responds with two random teams")
    async def on_message(ctx: commands.Context) -> None:
        """
        (2) 5 champ teams with roles based on where they normally play
        """
        response = ""
        for side in "AB":
            squad = "\n> ".join(make_team(champ_positions))
            response += f"Side {side}\n> {squad}\n"

        await ctx.send(response)

    @bot.command(
        name="chaos",
        help="Responds with two fully random teams (positions and damage type).",
    )
    async def on_message(ctx: commands.Context) -> None:
        """
        (2) 5 champ teams with roles and builds fully random
        """
        response = ""
        for side in "AB":
            squad = "\n> ".join(make_chaos(champs))
            response += f"Side {side}\n> {squad}\n"

        await ctx.send(response.strip())  # Remove tailing '\n'

    @bot.command(
        name="jailtime",
        help="Get the total amount of time the user has spent in timeout.",
    )
    async def on_message(ctx: commands.Context, *args: discord.Member) -> None:
        """
        How long the supplied users have been in jail.
        """
        if args:
            # Show a user or multiple users
            response: list[str] = []
            for user in args:
                timeouts, total_time, _ = get_user_timeout_data(user)
                hours, minutes = divmod(total_time, 3600)
                minutes, seconds = divmod(minutes, 60)
                response.append(
                    f"{user.mention} has been in timeout {timeouts} times for {hours}:{minutes}:{seconds}."
                )
        else:
            # Show the leaderboard
            leaderboard = get_timeout_leaderboard()
            if leaderboard:
                padding = max(
                    len(user)
                    for user in itertools.chain(leaderboard[0], leaderboard[1])
                )
                response = [
                    "Most timed out:",
                    "-" * padding,
                    leaderboard[0],
                    "-" * padding,
                    "Longest timed out:",
                    "-" * padding,
                    leaderboard[1],
                ]
            else:
                response = ["No timeouts yet."]
        await ctx.send("\n".join(response))

    @bot.event
    async def on_member_update(before: discord.Member, after: discord.Member) -> None:
        """
        Update the stored dictionary of user timeouts.
        Only takes action when changing from not in timeout to in timeout.
        """
        now = dt.datetime.now(dt.timezone.utc)
        if before.timed_out_until is not None:
            return
        if (ending := after.timed_out_until) is None:
            return
        with TIMEOUTS.open() as fp:
            data: dict[str, tuple[int, int, str]] = json.load(fp)
        existing = data.setdefault(after.name, (0, 0, after.display_name))
        data[after.name] = (
            existing[0] + 1,
            existing[1] + ((ending - now).seconds),
            after.display_name,
        )
        with TIMEOUTS.open("w+") as fp:
            json.dump(data, fp, indent=2)

    bot.run(bot_token, log_handler=handler)


if __name__ == "__main__":
    main()
