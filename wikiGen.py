import wikipedia

def randomWikiGen():
    random_title = wikipedia.random()
    try:
        page = wikipedia.page(random_title)
        return f"**{page.title}**\n{page.summary[:300]}...\nRead more: {page.url}"
    except wikipedia.exceptions.DisambiguationError as e:
        return f"Too many results for **{random_title}**. Try searching directly: https://en.wikipedia.org/wiki/{random_title.replace(' ', '_')}"
    except wikipedia.exceptions.PageError:
        return "Couldn't find a valid Wikipedia article. Try again!"