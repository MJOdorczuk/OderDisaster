def progress_bar(current, total, bar_length=20):
     fraction = current / total
     arrow = int(fraction * bar_length - 1) * "=" + ">"
     padding = int(bar_length - len(arrow)) * " "
     ending = "\n" if current == total else "\r"
     print(f"[{arrow}{padding}] {int(fraction*100)}% ({current}/{total})", end=ending)
     print("\r") # Ugly, but makes the progress bar (hopefully) always visible