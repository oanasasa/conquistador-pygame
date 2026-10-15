import json
import random
from pathlib import Path

import pygame

pygame.init()
WIDTH, HEIGHT = 900, 600
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Conquistador prototype")
clock = pygame.time.Clock()
font = pygame.font.SysFont(None, 30)
big_font = pygame.font.SysFont(None, 42)

NUM_PLAYERS = 3
COLORS = [(220, 60, 60), (60, 120, 220), (60, 180, 80)]
BUZZ_KEYS = [pygame.K_a, pygame.K_l, pygame.K_SEMICOLON]   # one key per player
ANSWER_KEYS = [pygame.K_1, pygame.K_2, pygame.K_3]

def load_questions():
    path = Path(__file__).parent / "data" / "questions.json"
    with open(path, encoding="utf-8") as f:
        return [q for q in json.load(f) if q.get("reviewed")]

QUESTIONS = load_questions()

# Grid of regions (replace later with a real map)
GRID_COLS, GRID_ROWS = 4, 3
MARGIN = 20
CELL_W = (WIDTH - MARGIN * 2) // GRID_COLS
CELL_H = (HEIGHT - 150 - MARGIN) // GRID_ROWS
territories = []
for row in range(GRID_ROWS):
    for col in range(GRID_COLS):
        rect = pygame.Rect(MARGIN + col * CELL_W, 150 + row * CELL_H,
                           CELL_W - 4, CELL_H - 4)
        territories.append({"rect": rect, "owner": None})

def text(s, pos, color=(255, 255, 255), f=font):
    screen.blit(f.render(s, True, color), pos)

def new_question():
    global question, buzzed, locked_out
    question = random.choice(QUESTIONS)
    buzzed = None
    locked_out = set()

def check_winner():
    owners = {t["owner"] for t in territories}
    if len(owners) == 1 and None not in owners:
        return owners.pop()
    return None

state = "question"      # "question", "pick", or "over"
current_player = None
winner = None
new_question()

running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        # Buzzing in and answering
        if event.type == pygame.KEYDOWN and state == "question":
            if buzzed is None:
                for p, key in enumerate(BUZZ_KEYS):
                    if event.key == key and p not in locked_out:
                        buzzed = p
            else:
                for choice, key in enumerate(ANSWER_KEYS):
                    if event.key == key and choice < len(question["choices"]):
                        if choice == question["answer"]:
                            current_player = buzzed
                            state = "pick"
                        else:
                            locked_out.add(buzzed)
                            buzzed = None
                            if len(locked_out) == NUM_PLAYERS:
                                new_question()   # nobody got it, next question

        # Claiming a region
        if (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
                and state == "pick"):
            for t in territories:
                if t["rect"].collidepoint(event.pos) and t["owner"] != current_player:
                    t["owner"] = current_player
                    winner = check_winner()
                    if winner is not None:
                        state = "over"
                    else:
                        state = "question"
                        new_question()
                    break

    # Drawing
    screen.fill((30, 30, 40))
    for t in territories:
        color = COLORS[t["owner"]] if t["owner"] is not None else (90, 90, 90)
        pygame.draw.rect(screen, color, t["rect"])

    if state == "question":
        text(question["q"], (MARGIN, 20), f=big_font)
        choices = "    ".join(f"{i+1}) {c}" for i, c in enumerate(question["choices"]))
        text(choices, (MARGIN, 80))
        if buzzed is None:
            text("Buzz in: P1 = A   P2 = L   P3 = ;", (MARGIN, 115))
        else:
            text(f"Player {buzzed + 1} answers: press 1-3", (MARGIN, 115),
                 COLORS[buzzed])
    elif state == "pick":
        text(f"Player {current_player + 1}: click a region to claim it",
             (MARGIN, 60), COLORS[current_player], big_font)
    elif state == "over":
        text(f"Player {winner + 1} conquers the map!", (MARGIN, 60),
             COLORS[winner], big_font)

    pygame.display.flip()
    clock.tick(60)

pygame.quit()