import json
import random

def generate_balanced_cards(num_cards=400):
    columns = {
        'B': list(range(1, 16)),
        'I': list(range(16, 31)),
        'N': list(range(31, 46)),
        'G': list(range(46, 61)),
        'O': list(range(61, 76))
    }
    
    usage = {col: {n: 0 for n in nums} for col, nums in columns.items()}
    cards = []
    
    for card_num in range(1, num_cards + 1):
        card = []
        for letter in ['B', 'I', 'N', 'G', 'O']:
            nums = columns[letter]
            pick_count = 4 if letter == 'N' else 5
            sorted_nums = sorted(nums, key=lambda n: usage[letter][n])
            pool = sorted_nums[:15]
            random.shuffle(pool)
            picked = sorted(pool[:pick_count])
            
            for n in picked:
                card.append([letter, n])
                usage[letter][n] += 1
            
            if letter == 'N':
                card.insert(-2, ['N', None])
        
        grid = [card[i*5:(i+1)*5] for i in range(5)]
        cards.append({"card_number": card_num, "grid": grid})
    
    return cards

if __name__ == "__main__":
    cards = generate_balanced_cards(400)
    with open("data/bingo_cards.json", "w") as f:
        json.dump(cards, f, indent=2)
    print(f"Generated {len(cards)} cards")
