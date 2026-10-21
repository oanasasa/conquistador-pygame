# Conquistador - Game Rules

## Overview

Conquistador is a quiz-based territory game for 2 to 3 players, each on their
own computer on the same local network (LAN). Players answer general
knowledge questions to grab free land, then attack each other's regions and
castles. The game ends when one player controls every region.

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
  picks a random free region after 3 to 9 seconds, like a person thinking, and
  answers bonus questions after a few seconds, correctly about 60% of the time.

## Setup

- The map is Romania, drawn as an old parchment map. Its 42 counties are
  grouped into 20 regions (lands) such as Maramureș, Banat, Oltenia, Bucovina
  and Dobrogea. County borders are drawn faintly; only lands are played.
- All lands start unclaimed (plain parchment).
- Questions are drawn at random from `data/questions.json`.

## Opening: choosing starting regions

1. When the host starts, every player has 15 seconds to pick one region.
2. Picks are secret. A player can change their pick while others are still
   choosing.
3. The round ends as soon as every player has picked, or when the 15 seconds
   run out. All picks are then revealed at once. A region picked by only one
   player goes to that player.
4. If 2 or 3 players picked the same region, they play a bonus question for it:
   - All of them see the question at the same moment and answer with `1`-`4`
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
7. When every player owns one starting region, that region becomes their
   **base**: a castle with 3 towers. The land grab begins.

Two lands are neighbors when they share a border. Lands that only touch at a
single point are not neighbors.

## Land grab

Played while any region is still free. Players cannot attack each other yet.

1. Each round, every player has a fixed 10 seconds to select one free region
   next to their land. The round never ends early.
2. Selections are visible to everyone. The first player to select a region
   locks it, shown hatched in that player's color, and nobody else can select it.
   A player can change their selection, which releases the old region.
3. When the 10 seconds are up, everyone who selected a region answers the same
   question (keys `1`-`4` or click), with 10 seconds to answer.
4. Each player who answers correctly takes the region they selected. A wrong
   answer or no answer means no region this round.
5. If nobody selected anything, a new round starts.
6. When no free region is left, the war begins.

## War

1. Players take turns in a fixed order. On your turn you have a fixed
   10 seconds to choose one enemy region next to your land. You can change your
   choice until the time is up. If you choose nothing, your turn is skipped.
2. **Normal region:** you duel its owner with one question. The quickest
   correct answer wins, and a wrong answer locks that player out of the
   question. If you win, you take the region. If the owner wins, both answer
   wrong, or time runs out, the owner keeps it.
3. **Base:** attacking a base is a siege of up to 3 duel questions in a row,
   one per tower. Each question you win destroys a tower. Questions the
   defender wins, or that nobody wins, leave the tower standing.
4. Destroyed towers stay destroyed, so other players can finish off a weakened
   base on later turns.
5. When a base's last tower falls, the attacker takes all of that player's
   land and that player is out of the game.
6. Other players watch every duel and see the question but cannot answer.

## Who was faster

These apply to every duel, both the opening bonus questions and the war duels:

- Questions pop up over the dimmed map with a countdown bar.
- When a player wins a duel, the question stays open for up to 3 more seconds.
  A player who hasn't answered yet can still answer to see if they were right,
  but it can't change the result. The game moves on as soon as everyone has
  answered.
- After each question, a result card shows every answer: right or wrong, the
  time taken, who was first, and how much slower the other correct answers
  were (for example "correct, but 0.4s slower").

## Winning

- The last player standing owns the whole map and wins.

## Question rules

- Questions must be general knowledge with short, unambiguous answers.
- Each question has three or four choices with one correct answer.
- Before creating a room, the host chooses the question categories (History,
  Art, Mythology; at least one) and the difficulty (Any, Easy, Medium or Hard).
  Questions are then fetched from the Open Trivia Database (opentdb.com). The
  room can start once the first questions have arrived. Without internet the
  game uses its built-in questions.
- The question card shows each question's category and difficulty.
- Built-in questions are stored in `data/questions.json` and marked
  `"reviewed": true` only after the owner has checked them.

## Fair play

- Phones and other devices must be put away during play.
- Players may not discuss answers while a question is open.
- The owner decides any disputed answer, and the decision is final.

## Open questions

- How long should questions stay open (currently 10 seconds)?
- Should the war turn order rotate who goes first each game?
