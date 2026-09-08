import random

import discord
from discord import app_commands

from utils import components

"""
1 in 10 chance to fail lol
"""

sassy_replies = [
    "Sandrone has determined that this command is beneath her.",
    "Sandrone is tired of your command usage. Ask again nicely and she might do it.",
    "No.",
    "Absolutely not.",
    "Sandrone has decided that you have used enough commands today.",
    "The puppet has reviewed your request. It has declined.",
    "Your command has been rejected on the grounds that Sandrone doesn't feel like it.",
]

class SassyDenial(app_commands.CheckFailure):
    pass

async def sassy(interaction: discord.Interaction) -> bool:
    if random.randint(1, 10) != 1:
        return True

    await interaction.response.send_message(
        view=components.panel(
            body=(
                "<:sandrone_refuses:1546669792595939468> "
                f"{random.choice(sassy_replies)}"
            ),
            color=discord.Color.gold(),
        )
    )

    raise SassyDenial()

sassy = app_commands.check(sassy)


"""
Used for the /judge command
"""

judge_certain_user = {
    1025770042245251122: "Sandrone chooses not to comment on her creator.",
    1542295080524845148: "The puppet decided that the real Sandrone is much nicer."
}

judge_replies = [
    "Sandrone has reviewed the evidence. She is unconvinced.",
    "The puppet has observed this individual. Further investigation is recommended.",
    "Verdict: suspicious.",
    "Sandrone has decided that this person is probably fine. Probably.",
    "The puppet finds them tolerable.",
    "Verdict: acceptable. Do not get excited.",
    "Sandrone has no objections at this time.",
    "The puppet has reviewed the subject and would like to keep them at a safe distance.",
    "Verdict: mildly concerning.",
    "Sandrone has determined that this individual requires supervision.",
    "The puppet approves. She doesn't know why.",
    "Sandrone has reached a verdict. Unfortunately, it is complicated.",
    "Verdict: guilty of being annoying.",
    "Sandrone has found insufficient evidence to justify throwing them out of the workshop.",
    "The puppet has considered the matter carefully. The answer is 'eh.'",
    "Verdict: suspiciously competent.",
    "Sandrone has determined that this person may remain. For now.",
    "The puppet has no comment. This is somehow worse than a comment.",
    "Verdict: needs further testing.",
    "Sandrone has inspected the subject. The results are inconclusive.",
    "The puppet says they are fine. The puppet is not a qualified judge.",
    "Verdict: surprisingly tolerable.",
    "Sandrone has decided that this person is not worth the paperwork.",
    "The puppet has filed them under 'probably harmless.'",
    "Verdict: workshop access denied.",
    "Sandrone has determined that this individual has potential. Whether that is good or bad remains unclear.",
    "The puppet has seen enough. Judgment rendered.",
    "Verdict: guilty of something. Sandrone will determine what later.",
    "Sandrone has decided to give them the benefit of the doubt. She already regrets it.",
    "The puppet has reviewed their behaviour and would like to speak to their manager.",
    "Verdict: questionable.",
    "Sandrone sees no reason to panic. Yet.",
    "The puppet has classified this person as 'interesting.' This is not necessarily a compliment.",
    "Verdict: acceptable specimen.",
    "Sandrone has determined that they may continue existing.",
    "The puppet has reviewed the subject and recommends keeping all valuable tools locked away.",
    "Verdict: too powerful. Keep an eye on them.",
    "Sandrone has decided that this person is allowed within five metres of the workshop.",
    "The puppet has reached a conclusion. Nobody asked what it was.",
    "Verdict: Sandrone will tolerate them.",
    "Sandrone has determined that this person is either a genius or a complete idiot.",
    "The puppet cannot tell which. Further testing required.",
    "Verdict: unexpectedly based.",
    "Sandrone has judged this person. The court is adjourned.",
    "The puppet has spoken. You probably shouldn't ask what it said.",
    "Verdict: needs more data.",
    "Sandrone has determined that this individual is harmless. The puppet disagrees.",
    "The puppet has awarded them one point. Nobody knows what the points are for.",
    "Verdict: tolerable. Barely.",
]

def judge(interaction: discord.Interaction, user: discord.abc.User) -> str:
    uid = user.id
    if uid in judge_certain_user:
        return judge_certain_user[uid]
    elif uid == interaction.client.user.id:
        return "Sandrone thinks she is the best person ever"
    rng = random.Random(uid)
    verdict = rng.choice(judge_replies)
    return verdict