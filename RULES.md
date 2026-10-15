# Conquistador - Game Rules

## Overview

Conquistador is a quiz-based territory game for 2 to 3 players sharing one
keyboard. Players buzz in to answer general knowledge questions. The correct
answerer claims a region on the map. The game ends when one player controls
every region.

## Players

- 2 or 3 players.
- Each player has a dedicated buzz key:
  - Player 1: `A`
  - Player 2: `L`
  - Player 3: `;`
- Each player has a color (red, blue, green) shown on the regions they own.

## Setup

- The map starts with all regions unclaimed (neutral gray).
- Questions are drawn at random from `data/questions.json`.
- Players agree before the game starts on the number of players.

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

- Should the first claim in a game be free (any region), or should players
  start in fixed positions?
- How many seconds should the time limit be?
- Should a wrong answer cost the player their next claim?
