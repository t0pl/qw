import requests
from urllib.parse import urlparse, parse_qs, urlencode
from bs4 import BeautifulSoup
import bullet
import re
import time
import os

headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/604.1 Edg/91.0.100.0"
    }


def check_response(q):
    if not q.ok:
        raise ValueError(
            f"Failed: {q.url} {q.status_code} {q.request.headers}")
    if len(q.content) == 0:
        raise ValueError(
            f"Warning:  Empty response from {q.url}"
        )


def ids(url):
    eid = parse_qs(urlparse(url).query)["ep"][0]
    mid = eid.split('_')[0]
    return eid, mid


def main(eid):
    print(sources(*embed(eid)))


def episodes(mid):
    global q, soup
    q = requests.get(
        f"https://fmovies.kim/ajax/movie_episodes/{mid}", headers=headers)
    check_response(q)

    html = q.json()['html']

    soup = BeautifulSoup(html,"html.parser")
    _episodes = {}
    for link in soup.find_all('a', {"id": True, "title": True, "data-id": True}):
        eid = link.get("data-id")
        episode=parse_episode_num_with_eid(eid)
        title=link.get('title')
        text=link.text

        if episode not in _episodes:
            _episodes[episode] = []
        _episodes[episode].append({"id": eid, "title": title, "text": text})

        #_episodes[eid] = {"id": eid, "title": title, "text": text}

    return _episodes


def search(keyword):
    q = requests.post("https://fmovies.kim/ajax/suggest_search",
                      data={"keyword": keyword}, headers=headers)
    check_response(q)

    html = q.json()['content']

    for a_element in BeautifulSoup(html,'html.parser').find_all('a', href=True):
        if len(a_element.text) != 0:
            yield {"url": "https://fmovies.kim"+a_element.get('href'), "title": a_element.text}


def embed(eid):
    global res
    res = requests.get(
        f"https://fmovies.kim/ajax/movie_embed/{eid}", headers=headers)
    check_response(res)
    return res.url, res.json()['src']


def check_available(source):

    if not source:
        print("Empty source")
        return False
    headers.update({"Referer":"https://fmovies.kim"})
    if not requests.head(source, headers=headers).ok:
        print("Bad response from", source)
        return False
    
    return True

def run(cmd):
    print("-"*20)
    print(cmd)
    os.system(cmd)

def auto_merge_and_upload():
    name = lambda x: x.split('/')[-1]
    name_mp4, name_sub = name(vid), name(sub)
    final_name = episode_choice.strip()+".mp4"
    print(name_mp4, name_sub, final_name)

    run(curl(vid, name_mp4))
    run(curl(sub, name_sub))
    run("snap install ffmpeg")
    run(ffmpeg(name_mp4, name_sub, final_name))
    run(upload(final_name))
    run(clear_downloaded_files(name_mp4, name_sub))

def clear_downloaded_files(*names):
    return 'rm -f '+' '.join(names)

def base_url(url):
    return "/".join(url.split('/')[:3])

def ffmpeg(mp4, subtitles, final_name):
    return f'ffmpeg -y -i "{mp4}" -i "{subtitles}" -c copy -c:s mov_text "{final_name}" -f mp4'

def upload(final_mp4):
    return f"curl --upload-file '{final_mp4}' https://transfer.sh"

def curl(url, filename, referer=""):
    output = f'curl "{url}" --output "{filename}"'
    if referer:
        output+=f' -e "{referer}"'
    return output

def lua(url, referer, output_file):
    with open(output_file, 'w') as f:
        f.write(f"""
        #EXTVLCOPT:http-referrer={referer}
        {url}
        """)
def parse_video(text):
    video = re.findall(r"https{0,1}:\/\/[^\s'\"]*\.(?:mp4|m3u8)",text)
    print("regex", video)
    if len(video) == 0:
        try:
            config = text.split('var config = {')[1].split('};')[0].split('file":"')
            video = config[1].split('"')[0]
        except IndexError:
            video = ""
    else:
        video = video[0]
    return video

def parse_subtitles(text):
    subtitles = re.findall(r"https{0,1}:\/\/[^\s'\"]*\.(?:vtt|txt|ssa|ttml|sbv|srt)",text)
    print("regex", subtitles)
    if len(subtitles) == 0:
        try:
            config = text.split('var config = {')[1].split('};')[0].split('file":"')
            subtitles = config[-1].split('"')[0]
        except IndexError:
            subtitles = ""
    else:
        subtitles = subtitles[0]
    return subtitles

def parse_fallback(text):
    fallback = re.findall(r"window\.location\s*=\s*['\"](https{0,1}:\/\/[^\s'\"]*)",text)
    print("regex", fallback)
    if len(fallback) == 0:
        global soup
        soup = BeautifulSoup(text, "html.parser")
        try:
            new_fallback = soup.find_all("iframe")[0].get('src')
        except IndexError:
            new_fallback = ""
        print("well inside")
        return new_fallback
    else:
        fallback = fallback[0]
    return fallback

def parse_sources(text):
    text = text.replace("\\/","/")

    video = parse_video(text)

    subtitles = parse_subtitles(text)
    
    #fallback = parse_fallback(text)
    
    for i in {"video", "subtitles"}:
        if len(eval(i)) == 0:
            print("Need another", i)
    

    return video, subtitles

def check_sources(video, subtitles):
    try_again = False

    for var in {"video", "subtitles"}:
        if not check_available(eval(var)):
            try_again = True
        else:
            print(eval(var))
    
    return try_again

    
    
def sources(ref, src, is_fallback=False):
    if not is_fallback:
        print("Trying", src)

    global q
    
    headers.update({"Referer": ref})
    q = requests.get(src, headers=headers)
    headers.pop("Referer")
    
    check_response(q)
    
    video, subtitles = parse_sources(q.text)

    sources_not_available = check_sources(video, subtitles)
    
    
    if sources_not_available:
        fallback = parse_fallback(q.text)
        if fallback:
            print("Fallback to", fallback)
            return sources(src, fallback, is_fallback=True)
        else:
            print("Guessing fallback")
            return sources(base_url(src), src.replace('/embed-player/','/ajax/getSources/'))
    
    return video, subtitles


def parse_mid_from_url(url):
    return url.split('-')[-1].replace('/', '')


def sort_episodes(_episodes):
    
    titles = set(j.get('title') for i in _episodes for j in _episodes[i])
    if len(_episodes) == 1:
        return list(titles)
    
    #change that
    def by_episode_num(x): return int(
        re.findall(r'pisode\s+\w{1,2}', x)[0].replace('pisode', '').strip()
    )

    return sorted(titles, key=by_episode_num)


def parse_episode_num_with_eid(eid):
    # 19768_10_3 -> 10
    return int(eid.split('_')[1])


def season(mid):
    all_episodes = episodes(mid)
    episode_ids = set(all_episodes.keys())
    print(episode_ids)

    for episode in episode_ids:
        print(episode)
        ref, episode_embedded_url = embed(episode)
        vid, sub = sources(ref, episode_embedded_url, is_fallback=True)
        print(vid, sub, "--"*10, sep="\n")

def best_episode(mid):
    global all_episodes
    all_episodes = episodes(mid)

    for eid in all_episodes:
        try:
            ref, episode_embedded_url = embed(eid)
            vid, sub = sources(ref, episode_embedded_url)
        except Exception as e:
            print("Next")
            with open("errors","a") as f:
                f.write(str(e))

def choose_series():
    search_kw = input('Search-$ ')
    if search_kw == "":
        raise ValueError("Empty Search")
    search_results = list(search(search_kw))
    series_choice = bullet.Bullet("Choose the path of least resistance", choices=[
                                  i.get('title') for i in search_results]).launch()
    # bullet.utils.clearConsoleUp(len(search_results)+2)
    return search_results,series_choice

def choose_episode(episodes_available):
    choices = sort_episodes(episodes_available)
    episode_choice = bullet.Bullet(
        "Choose the path of least resistance", choices=choices
    ).launch()
    # bullet.utils.clearConsoleUp(len(episodes_available)+2)
    return episode_choice

def find_url_matching_series(search_results, series_choice):
    #next(filter(lambda result: result.get('title') == series_choice, search_results)).get('url')
    
    for i in search_results:
        if i.get('title') == series_choice:
            return i.get('url')

def find_eids_matching_episode(episodes_available, episode_choice):
    return list(
        j.get('id') for i in episodes_available for j in episodes_available.get(i) if j.get('title') == episode_choice
    )

def choose_eid(eids):
    return bullet.Bullet(
        "Choose the path of least resistance", choices=eids
    ).launch()

def interactive():

    search_results, series_choice = choose_series()
    print(series_choice)

    url_matching_choice = find_url_matching_series(search_results, series_choice)
    print(url_matching_choice)

    mid = parse_mid_from_url(url_matching_choice)
    print(mid)

    episodes_available = episodes(mid)
    print(len(episodes_available), "episodes available")

    global episode_choice, vid, sub
    episode_choice = choose_episode(episodes_available)

    print(episode_choice)

    eids = find_eids_matching_episode(episodes_available, episode_choice)
    eid_choice = choose_eid(eids)

    ref, episode_embedded_url = embed(eid_choice)
    vid, sub = sources(ref, episode_embedded_url)

    print(f"\t{vid=}\n\t{sub=}")

if __name__ == "__main__":
    interactive()
    #"python3 -m pip install bs4 bullet"