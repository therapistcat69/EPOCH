"""Vocabulary and templates for the synthetic gaming-transcript generator.

Everything here is plain data. 'Ideas' (strategy/fact/route/opinion/stat) have several wordings that share
content words but differ in surface form, so a RECAP cue can restate an earlier idea in new words - the case
semantic (embedding) repetition features are meant to catch.
"""

GAMES = {
    "Elden Ring": dict(sub="action-rpg", enemies=["Malenia", "Margit", "Radahn", "Godrick", "Rennala", "Mohg"],
                       items=["greatsword", "spirit ash", "talisman", "katana", "sacred flask", "bow"],
                       places=["Limgrave", "Caelid", "the Haligtree", "Leyndell", "Stormveil Castle"],
                       mechs=["dodge roll", "parry", "poise", "stamina", "summon"]),
    "Minecraft": dict(sub="sandbox", enemies=["the Ender Dragon", "the Warden", "a creeper", "the Wither", "a ghast", "a pillager"],
                      items=["diamond pickaxe", "elytra", "netherite sword", "shield", "ender pearl", "totem"],
                      places=["the Nether", "an ancient city", "the End", "a mineshaft", "my base"],
                      mechs=["redstone", "enchanting", "crafting", "mob farm", "hunger bar"]),
    "Fortnite": dict(sub="battle royale", enemies=["a sweaty squad", "the final circle", "a boss NPC", "a pro player", "a camper", "a sniper"],
                     items=["shotgun", "shield potion", "launch pad", "assault rifle", "mythic medallion", "build kit"],
                     places=["Tilted Towers", "the storm edge", "the island", "a hot drop", "the vault"],
                     mechs=["box fighting", "edit speed", "high ground", "zone rotation", "material farming"]),
    "Valorant": dict(sub="tactical shooter", enemies=["the enemy Jett", "a Reyna", "the entire team", "an Operator", "a flanker", "their Sage"],
                     items=["Vandal", "Phantom", "smoke", "flash", "ultimate", "Sheriff"],
                     places=["A site", "B site", "mid", "Ascent", "Haven", "spawn"],
                     mechs=["crosshair placement", "economy", "peeking", "spray control", "utility"]),
    "GTA Online": dict(sub="open world", enemies=["the cops", "a rival crew", "a griefer", "a heist guard", "the helicopter", "a bounty hunter"],
                       items=["armored car", "oppressor", "sticky bombs", "rocket launcher", "sports car", "parachute"],
                       places=["Los Santos", "the casino", "Cayo Perico", "the docks", "the airfield"],
                       mechs=["heist planning", "wanted level", "mission setup", "stunt jumps", "vehicle upgrades"]),
    "Hollow Knight": dict(sub="metroidvania", enemies=["the Hollow Knight", "Hornet", "Mantis Lords", "the Radiance", "Soul Master", "Nosk"],
                          items=["nail", "dash charm", "soul vessel", "lantern", "crystal heart", "pale ore"],
                          places=["Greenpath", "the Deepnest", "the City of Tears", "the Abyss", "Hallownest"],
                          mechs=["pogo", "soul focus", "charm slots", "wall jump", "nail arts"]),
    "Among Us": dict(sub="social deduction", enemies=["the impostor", "a sus player", "the whole lobby", "a sneaky vent user", "my best friend", "the quiet one"],
                     items=["task list", "emergency button", "vent", "admin map", "security cameras", "sabotage"],
                     places=["Electrical", "Medbay", "the cafeteria", "Reactor", "O2"],
                     mechs=["voting", "alibis", "task timing", "vent spotting", "chat accusations"]),
    "Zelda: Tears of the Kingdom": dict(sub="adventure", enemies=["Ganondorf", "a Lynel", "the Gloom Hands", "a Talus", "a Hinox", "a Gleeok"],
                                        items=["Master Sword", "Ultrahand build", "hover bike", "fuse arrow", "paraglider", "zonai device"],
                                        places=["the Depths", "the Sky Islands", "Hyrule Castle", "Gerudo Desert", "Death Mountain"],
                                        mechs=["Ultrahand", "Fuse", "Recall", "Ascend", "stamina wheel"]),
    "Apex Legends": dict(sub="battle royale", enemies=["a Wraith", "the ring", "a full squad", "a Pathfinder", "a sniper nest", "the champion team"],
                         items=["Kraber", "Peacekeeper", "gold armor", "heirloom", "Havoc", "shield cell"],
                         places=["Olympus", "Storm Point", "World's Edge", "Kings Canyon", "the drop ship"],
                         mechs=["movement tech", "ability timing", "third partying", "ranked points", "slide jumping"]),
    "Dark Souls": dict(sub="action-rpg", enemies=["Ornstein", "Artorias", "the Taurus Demon", "Gwyn", "a black knight", "Sif"],
                       items=["estus flask", "dragon slayer sword", "ring of favor", "pyromancy flame", "shortbow", "ember"],
                       places=["Anor Londo", "Blighttown", "Firelink Shrine", "the Catacombs", "Lordran"],
                       mechs=["backstab", "weapon durability", "bonfire resting", "lock on", "stat scaling"]),
    "Rocket League": dict(sub="sports", enemies=["the other team", "a diamond player", "the final overtime", "their goalie", "a bot swarm", "the clock"],
                          items=["boost pad", "octane", "fennec", "goal explosion", "decal", "wheels"],
                          places=["the middle of the pitch", "the back post", "the net", "the corner", "the roof"],
                          mechs=["flip reset", "boost management", "air dribble", "rotation", "wall shots"]),
    "Cyberpunk 2077": dict(sub="open world", enemies=["Adam Smasher", "a maelstrom gang", "a cyberpsycho", "the arasaka guards", "a netrunner", "Smasher's crew"],
                           items=["mantis blades", "sandevistan", "iconic pistol", "cyberdeck", "monowire", "military grade armor"],
                           places=["Night City", "the badlands", "Pacifica", "Japantown", "Afterlife"],
                           mechs=["hacking", "dialogue choices", "perk trees", "stealth", "crafting"]),
}

ADJ = ["insane", "beautiful", "brutal", "weirdly satisfying", "super tense", "chaotic", "clean", "ridiculous", "underrated", "stressful"]
OUTCOMES = ["a full clear with no deaths", "a world record attempt", "the rarest item in the game", "a flawless victory",
            "the secret ending", "a perfect run", "the hardest achievement", "a clutch win against all odds"]
BRANDS = ["NordShield VPN", "GameFuel energy drinks", "PixelGear keyboards", "TurboHost servers", "LevelUp Academy", "ClutchChair"]
CODES = ["CLUTCH", "GG10", "LEVELUP", "BOSSFIGHT", "SPEEDRUN", "NOOB"]
INTERJECTIONS = ["Dude!", "No way!", "Let's go!", "Oh my god!", "Wait, what?", "Come on!", "Seriously?", "That is wild!"]
FILLERS = ["um", "like", "you know", "basically", "sort of", "I mean", "honestly", "kind of", "right"]
GOALS = ["{outcome}", "survive {place} using only a {item}", "defeat {enemy} before the timer runs out",
         "find out if {mech} is actually worth it", "rank every {item} in {game}"]

# --------------------------------------------------------------------------- idea wordings (paraphrase sets)
IDEAS = {
    "strategy": [
        "The trick against {enemy} is to use your {mech} before it charges, then punish with the {item}.",
        "{enemy} always charges first, so timing your {mech} is the key, and the {item} finishes the job.",
        "To beat {enemy} you want to save your {mech} for the charge and then hit back with the {item}.",
    ],
    "fact": [
        "In {game} the {mech} system changes how every fight in {place} plays out.",
        "Every fight in {place} depends on the {mech} system in {game}, which is easy to overlook.",
        "{place} is where the {mech} system in {game} matters the most.",
    ],
    "route": [
        "The fastest route is through {place}, where you can pick up the {item} early.",
        "Go through {place} first, because the {item} is sitting there and saves you a ton of time.",
        "Picking the {item} up in {place} is the quickest way to get ahead.",
    ],
    "opinion": [
        "Honestly the {mech} in {game} feels {adj}, and it is the reason I keep coming back.",
        "I keep coming back to {game} because the {mech} feels so {adj}.",
        "The {mech} is {adj} in {game}, which is why this game hooks me every time.",
    ],
    "stat": [
        "The {item} deals about {n} percent more damage than anything else I have tried against {enemy}.",
        "Against {enemy} the {item} is roughly {n} percent stronger than the alternatives.",
        "Nothing beats the {item} here, it does around {n} percent extra damage on {enemy}.",
    ],
}

# --------------------------------------------------------------------------- event templates
EVENTS = {
    "HOOK": [
        "What if I told you we can beat {enemy} using only a {item}?",
        "By the end of this video we are going to get {outcome}, and I have never tried this before.",
        "This is the one {game} challenge that everyone said was impossible, so of course I am doing it.",
        "Stay until the end, because what happens against {enemy} is something I did not expect.",
        "Today we are attempting {outcome} in {game}, and honestly I might not make it.",
    ],
    "INTRO_FLUFF": [
        "Hey guys, welcome back to the channel.",
        "Before we start, make sure you are subscribed and have notifications turned on.",
        "So yeah, it has been a little while, thanks so much for all the support lately.",
        "Anyway, let us get into it, but first a quick update about the channel and what is coming this month.",
        "Welcome back everybody, I hope you are all having a good week.",
        "Quick shout out to everyone in the comments who suggested this one.",
    ],
    "GAMEPLAY_ACTION": [
        "I sprint into {place}, grab the {item}, and {enemy} spots me right away.",
        "Okay moving through {place} now, switching to the {item}, here we go.",
        "I roll left, swing the {item}, and {enemy} staggers back for a second.",
        "Heading toward {place} while keeping my eyes on {enemy}.",
        "Using the {item} on {enemy}, and it actually lands this time.",
        "Cutting around {place} to get a better angle on {enemy}.",
    ],
    "COMMENTARY": [
        "Honestly this part of {game} is one of my favourites because {place} feels so {adj}.",
        "I think a lot of people underestimate how {adj} the {mech} is in {game}.",
        "You can really tell the developers put a lot of work into {place}.",
        "It is funny, every time I come back to {game} I notice something new about the {mech}.",
        "Chat keeps asking me about the {item}, and I think it is better than people say.",
    ],
    "SUSPENSE": [
        "My health is almost gone and one wrong move means {enemy} finishes me.",
        "Okay, do not panic, just a little more, {enemy} is nearly down too.",
        "Everything depends on this next hit, and I can barely hold the controller.",
        "I can hear {enemy} getting closer and I have one {item} left.",
        "This is it, if I mess up the {mech} now the whole run is over.",
    ],
    "PAYOFF": [
        "Yes! That is it, {enemy} is down, we actually did it!",
        "No way, the {item} worked, I cannot believe that just happened!",
        "We got it! {outcome}, and I am literally shaking right now.",
        "That is the moment, right there, that is why I love {game}!",
        "Let's go! First try with the {item}, absolutely insane!",
    ],
    "FAIL": [
        "Oh no, no, no, I died again, that {mech} completely failed.",
        "Seriously? {enemy} hit me through the {mech}, that is so unfair.",
        "Okay that one is on me, I got greedy near {place}.",
        "And we are dead, back to the start, that is so frustrating.",
        "I lost the {item} on that attempt, which hurts a lot.",
    ],
    "JOKE": [
        "Okay that was the funniest thing, my {item} just flew off the map.",
        "I have never seen {enemy} walk into a wall that many times, it is incredible.",
        "Chat said I could not do it, and then {enemy} fell off {place}, so I guess they were wrong.",
        "That animation looks like my cat walking on the keyboard.",
        "I am officially the worst {game} player alive, and I am proud of it.",
    ],
    "TOPIC_SHIFT": [
        "Okay completely different topic, let us talk about the new {game} update.",
        "Switching gears for a second, here is how the ranking system works.",
        "Now something totally unrelated, I finally tried the {mech} in a different game.",
        "Let us pause the run and look at my setup, because people keep asking.",
    ],
    "SPONSOR": [
        "This video is sponsored by {brand}, and they have been awesome to work with.",
        "{brand} gives you {n} percent off with code {code}, and the link is in the description.",
        "If you want to try {brand} yourself, use code {code} to support the channel.",
        "Thank you to {brand} for making this video possible, go check them out.",
    ],
    "CTA": [
        "If you enjoyed this, smash the like button and subscribe.",
        "Drop a comment with your best {game} moment, I read every single one.",
        "Subscribe if you want to see me attempt the next {game} challenge.",
        "Share this with a friend who needs to see {enemy} get destroyed.",
    ],
    "FILLER": [
        "Um, so, yeah, like, let me just, you know, figure this out.",
        "Right, so, basically, I mean, give me a second here.",
        "Okay so, uh, where was I, honestly, sort of lost track.",
        "So, like, yeah, kind of waiting for this to load, you know.",
    ],
    "OUTRO": [
        "That is it for today, thanks so much for watching, and I will see you in the next one.",
        "Thanks for hanging out with me, take care of yourselves and I will catch you next time.",
        "And that wraps up this one, see you in the next video.",
    ],
}

# --------------------------------------------------------------------------- title / description templates per archetype
TITLES = {
    "fast_challenge": ["I Tried to Beat {game} Without Dying", "{game} But Every Mistake Ends the Run", "I Only Had 24 Hours to Finish {game}"],
    "gameplay_commentary": ["Chill {game} Gameplay With Commentary", "Playing {game} For the First Time", "Exploring {place} in {game}"],
    "story_driven": ["The Story of {game} Explained While I Play", "{game} Walkthrough Part {n}", "The Ending of {game} Hits Different"],
    "tutorial_guide": ["How to Beat {enemy} in {game} (Easy Guide)", "{game} Beginner's Guide: {mech} Explained", "Master the {mech} in {game}"],
    "reaction": ["Reacting to the Craziest {game} Clips", "My Honest Reaction to the New {game} Trailer", "Watching Chat's Best {game} Plays"],
    "tournament_highlights": ["{game} Tournament Highlights: Insane Finals", "Top Plays From the {game} Championship", "The Best {game} Clutches of the Week"],
    "boss_fight": ["Defeating {enemy} in {game} (Hardest Boss)", "{enemy} Boss Fight: 50 Attempts Later", "Can I Beat {enemy} With Only a {item}?"],
    "funny_montage": ["{game} Funny Moments Compilation", "When {game} Goes Completely Wrong", "{game} Fails That Made Me Laugh"],
    "strategy_explanation": ["The Best {mech} Strategy in {game}", "Why {item} Is Broken in {game}", "{game} Meta Breakdown: What Actually Works"],
    "review_style": ["{game} Review: Is It Worth Playing in 2026?", "Honest {game} Review After 100 Hours", "{game} Update Review: Better or Worse?"],
}
