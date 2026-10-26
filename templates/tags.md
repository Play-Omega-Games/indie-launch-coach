# Tag helper (Steam)

Steam rule: at least 5 tags before launch, up to 20 recommended. The top 5 carry the most weight, some filters use the first 15, and the top 20 shape similar-game suggestions.

Steps:
1. Start from `data/genres.json` hints for the owner's genre.
2. Add tags shared by at least two of the owner's comparable games.
3. Order: the 5 that best describe what the player does, then setting and mood, then features.
4. Remove any tag the store page cannot back up with a screenshot or line of text.
Output: a ranked list with one line on why each tag is there, plus the official tags page link.
