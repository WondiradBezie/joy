def check_for_win(card_grid, called_balls):
    marked = [[False]*5 for _ in range(5)]
    marked[2][2] = True
    
    for r in range(5):
        for c in range(5):
            if r == 2 and c == 2:
                continue
            letter, num = card_grid[r][c]
            if num and f"{letter}{num}" in called_balls:
                marked[r][c] = True
    
    # Rows
    for r in range(5):
        if all(marked[r]):
            return True, f"Row {r+1}"
    # Columns
    for c in range(5):
        if all(marked[r][c] for r in range(5)):
            return True, f"Column {c+1}"
    # Diagonals
    if all(marked[i][i] for i in range(5)):
        return True, "Diagonal ↘"
    if all(marked[i][4-i] for i in range(5)):
        return True, "Diagonal ↙"
    # Corners
    if marked[0][0] and marked[0][4] and marked[4][0] and marked[4][4]:
        return True, "Four Corners"
    
    return False, None
