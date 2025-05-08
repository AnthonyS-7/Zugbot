# About Zugbot

Zugbot is a bot made to host mafia games on FoL. It is currently experimental; if there are any bugs, report them to @Zugzwang and the game hosts.

[details="Voting"]

Votes are placed with the same syntax that is usually used by the VC plugin on FoL. Voting is plurality only. 

If the Votes Match VC Plugin parameter (at the bottom) is set to True, votes are resolved nearly the same way the VC plugin resolves them. The exceptions to this are:

- Votes that match no players will be removed.
- Characters that can't be in Discourse usernames are removed from votes before processing.

If the Votes Match VC Plugin parameter is set to False, then in addition to the above ways Zugbot differs from the VC plugin, Zugbot will also remove votes that are substrings of multiple playernames (and not an exact match for any of them). For example, a vote for 'g' when both "wrongboy" and "Zugzwang" are living players would be removed.

[/details]

[details="Action Submission & The Factional"]

- Actions are submitted on the forum, with the exception of the mafia factional kill.
- All publicly submitted actions need a ping to Zugbot. 
- Privately submitted actions do not need a ping to Zugbot.
- If multiple different actions are submitted in the same post, they will all be processed, but may end up out of order.
  - This is an issue only if multiple of those actions have instant effects.
  - If multiple actions for the same ability are submitted, exactly one will go through. It is not guaranteed which this is (so do not do this).
- If you have an action, the syntax needed to use it is explained in your rolecard.
- Instant actions should be processed in under a minute (likely within 10 seconds). Even if an action is not instant, it will provide immediate acknowledgement, to show it has been seen.
  - This applies even if the action has been roleblocked.
  - If an action does not do this:
    - You may have mistyped the syntax or mispelled a username 
    - There may be a bug in the bot (during testing, this is the most likely outcome)
    - Zugbot may have went offline
- The mafia factional kill is submitted in wolfchat on Discord, through the Discord bot there.
  - The command to submit the nightkill is "$nightkill [player]".
- The factional is mandatory and not assigned.

[/details]

[details="Health and Protection"]

- All players have a health value, which is initially set to 1.
- When a player's health goes to 0 or below, they die.
- All kills, unless otherwise specified, deal 1 damage.
- All protections, unless otherwise specified, protect from 1 damage. 
- Protection acts like a shield that is depleted before health is damaged.
- Unless roles change this, everyone's protection is reset to 0 at day start.

[/details]

[details="Willpower and Roleblocking"]

- All players have a willpower value, which is by default set to 0 (and can be negative).
- Some actions have a minimum required willpower to use - if your willpower is below the required amount, your action will fail.
  - Some actions do not have a minimum, and will work regardless of willpower.
- Unless otherwise specified, you the minimum willpower to use an action is 0.
- Roleblocks subtract an amount of willpower - if not specified, they subtract 1.
- Unless roles change this, everyone's willpower is reset to 0 at day start.

[/details]

[details="Focus and Redirection"]

- Every *ability* (not player!) has a focus value.
- Every instance of redirection from one player to another has:
  - the player who's being redirected to
  - a redirection strength
  - a value to increase the focus by, if the action is redirected (will be greater than 0)
- A target is repeatedly changed by redirections until there are no more redirects, or the focus exceeds or equals the redirection strength. In more detail: For each target of an action,
  - If the target has no redirection effects on them, stop. The target is not changed.
  - If the ability's focus is greater than or equal to the redirection strength, stop. The target is not changed.
  - If the target has a redirection and the ability's focus is less than the redirection strength, increase* the focus by the specified value, and change the target. Now, repeat the process with the new target.

*The focus is increased only for the purposes of this target's resolution. The focus will not have increased for the resolution of other targets, nor will it have permanently increased.

[details="Further Details"]

If an action has both an instant part, and a phase-end part, redirections are processed independently both times*, and each part has a seperate focus value.

*This means, if I target Zugbot, and:

- During the day, there's a redirection from Zugbot to Maybot, which is stronger than my instant focus value
- At day end, there's a redirection from Zugbot to Wrongboy, which is stronger than my phase-end focus value
- There are no redirection effects of sufficient strength on Maybot or Wrongboy, at the relevant times

Then, my instant action targets Maybot, and my phase-end action targets Wrongboy.

[/details]

[/details]

[details="Bot Commands"]

- All players have access to "/votecount". This can be submitted in your PM to request a votecount, which is posted in the main thread.
  - The player who requested the votecount is not stated.
  - Of course, do not spam this.
- The host has access to:
  - /modkill [player] - This modkills the target player.
  - /sub [current_player] [player_to_be_added] - This replaces current_player with player_to_be_added.

[/details]
