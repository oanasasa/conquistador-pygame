# Conquistador - Game Rules

## Overview

Conquistador is a quiz-based territory game for 2 to 3 players, each on their
own computer on the same local network (LAN). Players buzz in to answer
general knowledge questions. The correct answerer claims a region on the map. The game ends when one player controls
every region.

## Players

- 2 or 3 players, each on their own computer.
- Each player chooses a username when the game opens.
- Each player has a color (red, blue, green, in joining order) shown on the
  regions they own.

## Rooms

- One player creates a room. Their computer hosts the game and they play too.
- Other players see rooms on the local network listed automatically, or join
  by typing the host's IP address.
- A room holds at most 3 players. Nobody can join after the game starts.
- The host clicks Start once at least 2 players are in the room.
- The host can add computer players (bots) to fill empty seats, so one person
  can play alone. Bots count as players and follow the same rules. A bot
  picks a random free region and answers bonus questions after a few seconds,
  correctly about 60% of the time.

## Setup

- The map has 12 regions, all unclaimed (neutral gray) at the start.
- Questions are drawn at random from `data/questions.json`.

## Opening: choosing starting regions

1. When the host starts, every player has 15 seconds to pick one region.
2. Picks are secret. A player can change their pick until the timer ends.
3. When the timer ends, all picks are revealed at once. A region picked by
   only one player goes to that player.
4. If 2 or 3 players picked the same region, they play a bonus question for it:
   - All of them see the question at the same moment and answer with `1`-`3`
     or by clicking.
   - The quickest correct answer wins the region, judged by the order answers
     reach the host.
   - A wrong answer locks that player out of this question.
   - If everyone is wrong, or nobody answers within 10 seconds, a new bonus
     question is asked.
   - Players not in the duel see the question but cannot answer.
5. Losers of a bonus question get a new 15-second pick, limited to free
   regions. If they pick the same region again, another bonus question
   decides it.
6. A player who never picks gets a random free region once all duels are done.
7. When every player owns one starting region, the main game begins.

## Turn structure

Each round has two phases.

### 1. Question phase

1. A question appears with its answer choices (numbered 1 to 3).
2. Players may buzz in at any time after the question appears. The first
   player to buzz gets the chance to answer.
3. The buzzing player presses `1`, `2`, or `3` to answer within the time limit.
4. **Correct answer:** the player moves to the claim phase.
5. **Wrong answer:** the player is locked out of this question. Remaining
   players may buzz in.
6. If every player is locked out, no one claims a region. A new question starts.

### 2. Claim phase

1. The player who answered correctly clicks one region on the map.
2. The region becomes owned by that player, even if another player owned it.
3. A player cannot claim a region they already own.
4. A new question starts.

## Winning

- A player wins immediately when they own every region on the map.
- Check for a winner after each claim.

## Time limits

- Each question has a short time limit (recommended: 5 to 8 seconds) to
  discourage looking up answers.
- If the time runs out with no buzz, the question is skipped.

## Question rules

- Questions must be general knowledge with short, unambiguous answers.
- Each question has exactly three choices with one correct answer.
- Questions are stored in `data/questions.json` and marked `"reviewed": true`
  only after the owner has checked them.

## Fair play

- Phones and other devices must be put away during play.
- Players may not discuss answers while a question is open.
- The owner decides any disputed answer, and the decision is final.

## Open questions (to decide before the first full game)

- Which key buzzes in during the main game, now that each player has their
  own keyboard?
- How many seconds should the time limit be?
- Should a wrong answer cost the player their next claim?
