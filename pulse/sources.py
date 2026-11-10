"""The source catalog.

150+ publications across every section of a serious news app, with the topics
each one is trusted for, its home country and (approximate) editorial
perspective so the reader can compare coverage.

Feed URLs live in FEEDS_RAW.  The `topic` on a feed is a *hint*: ingested
articles are still classified by content, but the hint keeps a sports feed from
polluting the science section.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

TOPICS: tuple[tuple[str, str, str], ...] = (
    ("world", "World", "🌍"),
    ("us", "US News", "🇺🇸"),
    ("politics", "Politics", "🏛️"),
    ("business", "Business", "📈"),
    ("tech", "Tech", "💻"),
    ("science", "Science", "🔬"),
    ("space", "Space", "🚀"),
    ("health", "Health", "🩺"),
    ("climate", "Climate", "🌱"),
    ("sports", "Sports", "🏆"),
    ("culture", "Culture", "🎭"),
    ("entertainment", "Entertainment", "🎬"),
    ("music", "Music", "🎧"),
    ("gaming", "Gaming", "🎮"),
    ("education", "Education", "🎓"),
    ("money", "Money & Life", "💸"),
    ("food", "Food", "🍜"),
    ("travel", "Travel", "✈️"),
    ("opinion", "Opinion", "💬"),
)

TOPIC_LABELS = {slug: label for slug, label, _ in TOPICS}
TOPIC_ICONS = {slug: icon for slug, _, icon in TOPICS}
TOPIC_SLUGS = tuple(slug for slug, _, _ in TOPICS)

REGIONS = (
    "Global", "United States", "Canada", "United Kingdom", "Europe",
    "Middle East", "Africa", "South Asia", "East Asia", "Southeast Asia",
    "Latin America", "Oceania",
)

AUDIENCES = ("general", "teen", "student", "specialist")

LEANS = ("left", "center-left", "center", "center-right", "right", "state")

_SRC_COLUMNS = ("id", "name", "domain", "country", "region", "lean", "paywall", "audience", "topics", "about")
_FEED_COLUMNS = ("source_id", "topic", "url", "label")


@dataclass(frozen=True)
class Source:
    id: str
    name: str
    domain: str
    country: str
    region: str
    lean: str
    paywall: bool
    audience: str
    topics: tuple[str, ...]
    about: str
    feeds: tuple[tuple[str, str, str], ...] = field(default=())

    @property
    def site(self) -> str:
        return f"https://{self.domain}"

    @property
    def initials(self) -> str:
        words = [w for w in re.split(r"[^A-Za-z0-9]+", self.name) if w]
        if not words:
            return "N"
        if len(words) == 1:
            return words[0][:2].upper()
        return (words[0][0] + words[1][0]).upper()

    @property
    def primary_topic(self) -> str:
        for topic in self.topics:
            if topic in TOPIC_SLUGS:
                return topic
        return "world"

    @property
    def teen_friendly(self) -> bool:
        return self.audience in ("teen", "student")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "domain": self.domain,
            "site": self.site,
            "country": self.country,
            "region": self.region,
            "lean": self.lean,
            "paywall": self.paywall,
            "audience": self.audience,
            "topics": list(self.topics),
            "about": self.about,
            "initials": self.initials,
            "primary_topic": self.primary_topic,
            "feed_count": len(self.feeds),
        }


SOURCES_RAW = """\
bbc|BBC News|bbc.com|GB|United Kingdom|center|0|general|world,us,politics,business,tech,science,health,sports,culture,climate,education,travel|Britain's public broadcaster, strong on fast global reporting and explainers.
ap|Associated Press|apnews.com|US|United States|center|0|general|world,us,politics,business,sports,health|Not-for-profit wire service whose copy underpins much of the industry.
reuters|Reuters|reuters.com|GB|United Kingdom|center|0|general|world,business,politics,tech,sports,climate|Global wire agency known for fast, factual market and world coverage.
aljazeera|Al Jazeera English|aljazeera.com|QA|Middle East|center|0|general|world,politics,business,culture,sports|Qatar-based international network with deep Global South coverage.
dw|DW News|dw.com|DE|Europe|center|0|general|world,politics,business,tech,science,culture,climate|Germany's international public broadcaster.
france24|France 24|france24.com|FR|Europe|center|0|general|world,politics,business,culture|French international news channel in English.
euronews|Euronews|euronews.com|FR|Europe|center|0|general|world,politics,business,tech,climate,travel|Pan-European rolling news service.
unnews|UN News|news.un.org|INT|Global|center|0|general|world,politics,health,climate,education|Official news service of the United Nations.
who|World Health Organization|who.int|INT|Global|center|0|specialist|health,science,world,politics|Global public-health agency announcements and reports.
nature|Nature|nature.com|GB|Global|center|1|specialist|science,health,climate,tech,space|Flagship peer-reviewed science journal.
science|Science (AAAS)|science.org|US|Global|center|1|specialist|science,health,space,climate,tech|News from the AAAS journal Science.
sciencedaily|ScienceDaily|sciencedaily.com|US|Global|center|0|student|science,health,space,climate,tech|Research press releases rewritten for general readers.
phys|Phys.org|phys.org|US|Global|center|0|student|science,space,tech,climate|Physics, chemistry and technology research news.
quanta|Quanta Magazine|quantamagazine.org|US|Global|center|0|student|science,space,tech|Deep, beautiful features on maths, physics and biology.
scientificamerican|Scientific American|scientificamerican.com|US|United States|center-left|1|student|science,health,space,climate,tech|America's oldest science magazine.
newscientist|New Scientist|newscientist.com|GB|United Kingdom|center|1|student|science,space,health,tech,climate|Weekly science and technology magazine.
nautilus|Nautilus|nautil.us|US|Global|center|0|student|science,culture,space|Literary science writing about big ideas.
aeon|Aeon|aeon.co|GB|Global|center-left|0|student|science,opinion,culture|Long-form essays on philosophy, science and society.
smithsonian|Smithsonian Magazine|smithsonianmag.com|US|United States|center|0|student|culture,science,travel|History, science and culture from the Smithsonian.
atlasobscura|Atlas Obscura|atlasobscura.com|US|Global|center|0|teen|travel,culture,food|Wonder-filled stories about the world's hidden places.
natgeo|National Geographic|nationalgeographic.com|US|Global|center|0|teen|travel,science,climate,culture|Iconic photography and exploration journalism.
spacecom|Space.com|space.com|US|Global|center|0|student|space,science|Spaceflight, astronomy and skywatching news.
livescience|Live Science|livescience.com|US|Global|center|0|student|science,health,space|Everyday science explained well.
universetoday|Universe Today|universetoday.com|CA|Global|center|0|student|space,science|Independent space and astronomy reporting.
nasa|NASA|nasa.gov|US|United States|state|0|student|space,science,climate|Official mission and research updates.
esa|European Space Agency|esa.int|INT|Europe|state|0|student|space,science|Europe's space programme newsroom.
noaa|NOAA|noaa.gov|US|United States|state|0|student|climate,science,space|US oceans and atmosphere agency.
worldbank|World Bank|worldbank.org|INT|Global|state|0|student|business,world,politics,climate|Development data, reports and project news.
govuk|GOV.UK|gov.uk|GB|United Kingdom|state|0|specialist|politics,world,health,education,climate|Official UK government announcements.
eucommission|European Commission|ec.europa.eu|BE|Europe|state|0|specialist|politics,world,climate,tech,business|Official EU executive press releases.
nyt|The New York Times|nytimes.com|US|United States|center-left|1|general|world,us,politics,business,tech,science,health,sports,culture,climate,education,money,travel|America's paper of record, with strong visual and data journalism.
wapo|The Washington Post|washingtonpost.com|US|United States|center-left|1|general|us,politics,world,business,tech,sports,culture,health,climate|Washington powerhouse with sharp political and investigative reporting.
wsj|The Wall Street Journal|wsj.com|US|United States|center-right|1|general|business,politics,us,tech,money,world|Business-first daily with deep markets coverage.
cnn|CNN|cnn.com|US|United States|center|0|general|world,us,politics,business,tech,health,sports,culture|24-hour cable news pioneer.
npr|NPR|npr.org|US|United States|center-left|0|general|us,world,politics,business,tech,science,health,sports,culture,education|US public radio network with calm, explanatory reporting.
pbs|PBS NewsHour|pbs.org|US|United States|center|0|student|us,world,politics,science,education,health|US public television's nightly news programme.
usatoday|USA Today|usatoday.com|US|United States|center|0|general|us,world,sports,money,tech,travel|National US daily built for skimming.
nbc|NBC News|nbcnews.com|US|United States|center|0|general|us,politics,world,health,tech|US broadcast network news division.
abcnews|ABC News|abcnews.go.com|US|United States|center|0|general|us,world,politics,business,health|US broadcast network news division.
cbsnews|CBS News|cbsnews.com|US|United States|center|0|general|us,world,politics,health,tech|US broadcast network news division.
foxnews|Fox News|foxnews.com|US|United States|right|0|general|us,politics,world,money,sports,entertainment|US cable network with a conservative opinion line-up.
nypost|New York Post|nypost.com|US|United States|right|0|general|us,politics,entertainment,sports,money|Tabloid-energetic New York daily.
latimes|Los Angeles Times|latimes.com|US|United States|center-left|1|general|us,world,business,culture,sports,climate|West Coast metro daily with strong culture coverage.
politico|Politico|politico.com|US|United States|center|0|general|politics,us,world|Inside-the-room political reporting.
thehill|The Hill|thehill.com|US|United States|center|0|general|politics,us|Congress-focused political news.
axios|Axios|axios.com|US|United States|center|0|general|politics,business,tech,us,world|Bullet-point, "smart brevity" news.
propublica|ProPublica|propublica.org|US|United States|center-left|0|student|us,politics,business,health,climate|Investigative newsroom with free, high-impact stories.
motherjones|Mother Jones|motherjones.com|US|United States|left|1|general|politics,climate,culture|Investigative magazine with a progressive voice.
reason|Reason|reason.com|US|United States|right|0|general|politics,opinion,money|Libertarian magazine on policy and culture.
nationalreview|National Review|nationalreview.com|US|United States|right|1|general|politics,opinion|Foundational American conservative magazine.
vox|Vox|vox.com|US|United States|left|0|student|politics,culture,tech,science,health,money,climate|Explainers that answer "why is this happening?".
slate|Slate|slate.com|US|United States|left|0|student|culture,politics,tech|Smart, argumentative culture and politics writing.
salon|Salon|salon.com|US|United States|left|0|general|politics,culture|Progressive politics and culture site.
thedailybeast|The Daily Beast|thedailybeast.com|US|United States|left|0|general|politics,culture,entertainment|Fast-paced politics and scandal coverage.
huffpost|HuffPost|huffpost.com|US|United States|left|0|general|politics,culture,health|Progressive news and lifestyle site.
theintercept|The Intercept|theintercept.com|US|United States|left|0|general|politics,world,tech|Adversarial investigative journalism.
thenation|The Nation|thenation.com|US|United States|left|1|general|politics,opinion,culture|America's oldest weekly magazine of the left.
newsweek|Newsweek|newsweek.com|US|United States|center|0|general|us,world,politics,business|Global news weekly turned digital daily.
csmonitor|The Christian Science Monitor|csmonitor.com|US|United States|center|0|student|world,us,politics,science,culture|Measured global reporting with a solutions bent.
statnews|STAT|statnews.com|US|United States|center|1|specialist|health,science,politics|Sharp life-sciences and public-health journalism.
kff|KFF Health News|kffhealthnews.org|US|United States|center|0|specialist|health,politics|Non-profit health policy reporting.
harvardhealth|Harvard Health|health.harvard.edu|US|United States|center|0|student|health,science|Evidence-based health explainers from Harvard Medical School.
insidehighered|Inside Higher Ed|insidehighered.com|US|United States|center|0|student|education,politics|Higher-education news for students and staff.
edsurge|EdSurge|edsurge.com|US|United States|center|0|student|education,tech|Where education and technology meet.
hechinger|The Hechinger Report|hechingerreport.org|US|United States|center-left|0|student|education|Non-profit journalism about inequality and innovation in schools.
the74|The 74|the74million.org|US|United States|center|0|student|education,politics|Education news and analysis for US schools.
chalkbeat|Chalkbeat|chalkbeat.org|US|United States|center|0|student|education|Local, non-profit education reporting.
teenvogue|Teen Vogue|teenvogue.com|US|United States|left|0|teen|culture,politics,entertainment,education,money|Fashion magazine with a serious politics and culture desk.
seventeen|Seventeen|seventeen.com|US|United States|center|0|teen|culture,money,health|Lifestyle and advice for teens.
guardian|The Guardian|theguardian.com|GB|United Kingdom|left|0|general|world,us,politics,business,tech,science,health,sports,culture,climate,education,food,travel|Open-access British daily, strong on climate, science and culture.
independent|The Independent|independent.co.uk|GB|United Kingdom|center-left|0|general|world,politics,business,tech,sports,culture,travel|British digital daily with a liberal voice.
telegraph|The Telegraph|telegraph.co.uk|GB|United Kingdom|right|1|general|world,politics,business,sports,culture|British broadsheet with a conservative editorial line.
ft|Financial Times|ft.com|GB|United Kingdom|center|1|general|business,world,politics,money,tech|Salmon-pink bible of global finance.
economist|The Economist|economist.com|GB|United Kingdom|center|1|student|world,business,politics,tech,science,culture,money,climate|Weekly analysis with a strong data and charts habit.
skynews|Sky News|news.sky.com|GB|United Kingdom|center|0|general|world,us,politics,business,tech,sports|Rolling UK and world news.
mirror|The Mirror|mirror.co.uk|GB|United Kingdom|center-left|0|general|world,entertainment,sports|British tabloid with big entertainment coverage.
express|Daily Express|express.co.uk|GB|United Kingdom|right|0|general|world,politics,entertainment,health|British tabloid.
dailymail|Daily Mail|dailymail.co.uk|GB|United Kingdom|right|0|general|world,politics,entertainment,sports,health|Britain's biggest tabloid site.
metro|Metro|metro.co.uk|GB|United Kingdom|center|0|teen|entertainment,world,culture,sports|Free commuter paper built for quick reads.
standard|Evening Standard|standard.co.uk|GB|United Kingdom|center|0|general|world,business,culture,politics|London's evening newspaper.
scotsman|The Scotsman|scotsman.com|GB|United Kingdom|center|0|general|world,politics,business|Scotland's national newspaper.
rte|RTÉ|rte.ie|IE|Europe|center|0|general|world,sports,culture,politics|Ireland's public service broadcaster.
irishtimes|The Irish Times|irishtimes.com|IE|Europe|center|1|general|world,politics,business,culture|Ireland's paper of record.
the42|The42|the42.ie|IE|Europe|center|0|specialist|sports|Irish sport, brilliantly told.
spiegel|Der Spiegel|spiegel.de|DE|Europe|center-left|1|general|world,politics,business|Germany's leading news magazine.
zeit|Die Zeit|zeit.de|DE|Europe|center-left|1|general|world,politics,culture,education|German weekly known for long reads.
faz|FAZ|faz.net|DE|Europe|center-right|1|general|world,business,politics|Frankfurt broadsheet of record.
sueddeutsche|Süddeutsche Zeitung|sueddeutsche.de|DE|Europe|center-left|1|general|world,politics,business,culture|Munich daily with investigative muscle.
lemonde|Le Monde|lemonde.fr|FR|Europe|center-left|1|general|world,politics,business,culture,climate|France's paper of record, now with an English edition.
lefigaro|Le Figaro|lefigaro.fr|FR|Europe|center-right|1|general|world,politics,culture|France's oldest national daily.
liberation|Libération|liberation.fr|FR|Europe|left|1|general|politics,culture,world|French left-leaning daily.
elpais|El País|elpais.com|ES|Europe|center-left|1|general|world,politics,culture,sports|Spain's leading daily, with an English edition.
elmundo|El Mundo|elmundo.es|ES|Europe|center-right|1|general|world,politics,sports|Spanish daily with strong sports coverage.
ansa|ANSA|ansa.it|IT|Europe|center|0|general|world,politics,business|Italy's national wire service.
corriere|Corriere della Sera|corriere.it|IT|Europe|center|1|general|world,politics,culture|Italy's paper of record.
repubblica|la Repubblica|repubblica.it|IT|Europe|center-left|1|general|world,politics,culture|Major Italian daily.
dutchnews|DutchNews|dutchnews.nl|NL|Europe|center|0|general|world,politics,business|Dutch news in English.
thelocalde|The Local Germany|thelocal.de|DE|Europe|center|0|general|world,culture,politics|Germany news for English readers.
swissinfo|SWI swissinfo.ch|swissinfo.ch|CH|Europe|center|0|general|world,politics,business|Switzerland's international public broadcaster.
euobserver|EUobserver|euobserver.com|BE|Europe|center|0|specialist|politics,world|Independent reporting on the European Union.
politicoeu|Politico Europe|politico.eu|BE|Europe|center|0|general|politics,world,tech|Brussels' political insider coverage.
kyivindependent|The Kyiv Independent|kyivindependent.com|UA|Europe|center|0|general|world,politics|Ukrainian English-language newsroom.
moscowtimes|The Moscow Times|themoscowtimes.com|RU|Europe|center|0|general|world,politics|Independent Russian news in English.
timesofisrael|The Times of Israel|timesofisrael.com|IL|Middle East|center|0|general|world,politics|Independent Israeli news site.
jpost|The Jerusalem Post|jpost.com|IL|Middle East|center-right|0|general|world,politics|Israel's oldest English-language daily.
haaretz|Haaretz|haaretz.com|IL|Middle East|left|1|general|world,politics,culture|Israeli daily known for liberal commentary.
972mag|+972 Magazine|972mag.com|IL|Middle East|left|0|general|politics,world|Independent commentary from Israel-Palestine.
arabnews|Arab News|arabnews.com|SA|Middle East|center|0|general|world,business,politics,culture|Saudi-based English daily.
gulfnews|Gulf News|gulfnews.com|AE|Middle East|center|0|general|world,business,sports|Dubai-based daily.
khaleejtimes|Khaleej Times|khaleejtimes.com|AE|Middle East|center|0|general|world,business,sports|UAE daily.
thenational|The National|thenationalnews.com|AE|Middle East|center|0|general|world,politics,business,culture|Abu Dhabi-based daily.
middleeasteye|Middle East Eye|middleeasteye.net|GB|Middle East|center-left|0|general|world,politics|London-based Middle East outlet.
tehrantimes|Tehran Times|tehrantimes.com|IR|Middle East|state|0|general|world,politics|Iranian state-affiliated English daily.
hurriyet|Hürriyet Daily News|hurriyetdailynews.com|TR|Middle East|center|0|general|world,politics|Turkey's English-language daily.
dailysabah|Daily Sabah|dailysabah.com|TR|Middle East|center-right|0|general|world,politics|Turkish pro-government daily.
punch|Punch|punchng.com|NG|Africa|center|0|general|world,politics,business,sports|Nigerian daily with huge reach.
premiumtimes|Premium Times|premiumtimesng.com|NG|Africa|center|0|general|politics,world,business|Nigerian investigative news site.
vanguardngr|Vanguard|vanguardngr.com|NG|Africa|center|0|general|politics,world,business,sports|Nigerian daily.
myjoyonline|MyJoyOnline|myjoyonline.com|GH|Africa|center|0|general|politics,world,sports|Ghanaian news portal.
mg|Mail & Guardian|mg.co.za|ZA|Africa|center-left|1|general|politics,world,culture|South African weekly known for investigations.
dailymaverick|Daily Maverick|dailymaverick.co.za|ZA|Africa|center|1|student|politics,world,business|South African independent daily.
news24|News24|news24.com|ZA|Africa|center|1|general|world,politics,sports|South Africa's biggest news site.
eastafrican|The EastAfrican|theeastafrican.co.ke|KE|Africa|center|1|general|world,business,politics|Regional East African weekly.
nationafrica|Nation Africa|nation.africa|KE|Africa|center|0|general|world,politics,sports|Kenya's Nation Media Group.
ahram|Ahram Online|english.ahram.org.eg|EG|Africa|state|0|general|world,politics,culture|Egyptian state-linked English news.
moroccoworldnews|Morocco World News|moroccoworldnews.com|MA|Africa|center|0|general|world,politics|Morocco-focused English news.
toi|The Times of India|timesofindia.indiatimes.com|IN|South Asia|center-right|0|general|world,politics,business,tech,sports,entertainment,education|The world's largest English-language newspaper by circulation.
hindu|The Hindu|thehindu.com|IN|South Asia|center-left|1|general|world,politics,business,tech,science,sports,education|Chennai-based Indian daily of record.
ndtv|NDTV|ndtv.com|IN|South Asia|center|0|general|world,politics,business,tech,sports,entertainment|Indian rolling news network.
indianexpress|The Indian Express|indianexpress.com|IN|South Asia|center|1|general|world,politics,business,tech,sports,education|Indian daily with strong explanatory journalism.
hindustantimes|Hindustan Times|hindustantimes.com|IN|South Asia|center|0|general|world,politics,business,entertainment,sports,education|Indian national daily.
scroll|Scroll.in|scroll.in|IN|South Asia|center-left|0|general|politics,culture,world|Independent Indian digital news.
thewire|The Wire|thewire.in|IN|South Asia|left|0|general|politics,world,culture|Indian non-profit news site.
livemint|Mint|livemint.com|IN|South Asia|center|1|general|business,money,tech,politics|Indian business daily.
firstpost|Firstpost|firstpost.com|IN|South Asia|center-right|0|general|world,politics,entertainment,sports|Indian digital news outlet.
dawn|Dawn|dawn.com|PK|South Asia|center|0|general|world,politics,business|Pakistan's oldest English daily.
tribune|The Express Tribune|tribune.com.pk|PK|South Asia|center|0|general|world,politics,sports|Pakistani English daily.
kathmandupost|The Kathmandu Post|kathmandupost.com|NP|South Asia|center|0|general|world,politics|Nepal's English daily.
dailystar|The Daily Star|thedailystar.net|BD|South Asia|center|0|general|world,politics,culture|Bangladesh's leading English daily.
dailymirror|Daily Mirror|dailymirror.lk|LK|South Asia|center|0|general|world,politics,sports|Sri Lankan English daily.
japantimes|The Japan Times|japantimes.co.jp|JP|East Asia|center|1|general|world,politics,business,culture|Japan's oldest English-language newspaper.
nhk|NHK World|www3.nhk.or.jp|JP|East Asia|state|0|general|world,politics,tech,culture|Japan's public broadcaster.
asahi|The Asahi Shimbun|asahi.com|JP|East Asia|center-left|1|general|world,politics,culture|Major Japanese daily.
nikkei|Nikkei Asia|asia.nikkei.com|JP|East Asia|center|1|general|business,tech,world,politics|Asia's premier business publication.
koreaherald|The Korea Herald|koreaherald.com|KR|East Asia|center|0|general|world,politics,business,tech,culture|South Korea's English daily.
yonhap|Yonhap News|en.yna.co.kr|KR|East Asia|state|0|general|world,politics,business|South Korea's national news agency.
scmp|South China Morning Post|scmp.com|HK|East Asia|center|1|general|world,politics,business,tech|Hong Kong's English daily of record.
hkfp|Hong Kong Free Press|hongkongfp.com|HK|East Asia|center|0|general|politics,world|Independent Hong Kong news.
taipeitimes|Taipei Times|taipeitimes.com|TW|East Asia|center|0|general|world,politics|Taiwan's English-language daily.
straitstimes|The Straits Times|straitstimes.com|SG|Southeast Asia|center|1|general|world,politics,business,tech,education|Singapore's paper of record.
cna|CNA|channelnewsasia.com|SG|Southeast Asia|state|0|general|world,politics,business,tech,health|Singapore's regional news network.
jakartapost|The Jakarta Post|thejakartapost.com|ID|Southeast Asia|center|0|general|world,politics,business|Indonesia's English daily.
bangkokpost|Bangkok Post|bangkokpost.com|TH|Southeast Asia|center|0|general|world,politics,business|Thailand's English daily.
vnexpress|VnExpress International|e.vnexpress.net|VN|Southeast Asia|state|0|general|world,politics,business,culture|Vietnam's most-read news site.
inquirer|Philippine Daily Inquirer|newsinfo.inquirer.net|PH|Southeast Asia|center|0|general|world,politics,sports|The Philippines' largest daily.
rappler|Rappler|rappler.com|PH|Southeast Asia|center|0|general|politics,world,tech|Filipino independent digital newsroom.
abcau|ABC News (Australia)|abc.net.au|AU|Oceania|center|0|general|world,politics,business,tech,science,health,sports,culture,climate,education|Australia's public broadcaster.
smh|The Sydney Morning Herald|smh.com.au|AU|Oceania|center|1|general|world,politics,business,sports,culture|Sydney's paper of record.
theage|The Age|theage.com.au|AU|Oceania|center|1|general|world,politics,business,sports|Melbourne's daily.
guardianau|The Guardian Australia|theguardian.com|AU|Oceania|left|0|general|world,politics,climate,culture|Guardian's Australian edition.
sbs|SBS News|sbs.com.au|AU|Oceania|center|0|general|world,politics,culture,travel|Australia's multicultural broadcaster.
nzherald|NZ Herald|nzherald.co.nz|NZ|Oceania|center|1|general|world,politics,business,sports|New Zealand's biggest news site.
rnz|RNZ|rnz.co.nz|NZ|Oceania|center|0|general|world,politics,business,sports|New Zealand's public broadcaster.
cbc|CBC News|cbc.ca|CA|Canada|center|0|general|world,politics,business,tech,health,sports,culture,climate,education|Canada's public broadcaster.
globeandmail|The Globe and Mail|theglobeandmail.com|CA|Canada|center|1|general|world,politics,business|Canada's national newspaper.
nationalpost|National Post|nationalpost.com|CA|Canada|center-right|1|general|world,politics,business|Canadian conservative-leaning daily.
ctvnews|CTV News|ctvnews.ca|CA|Canada|center|0|general|world,politics,health,sports|Canada's private network news.
infobae|Infobae|infobae.com|AR|Latin America|center|0|general|world,politics,business,sports|Argentina's biggest digital news site.
clarin|Clarín|clarin.com|AR|Latin America|center|0|general|world,politics,sports,culture|Argentina's largest newspaper.
folha|Folha de S.Paulo|folha.uol.com.br|BR|Latin America|center|1|general|world,politics,business,culture|Brazil's paper of record.
eluniversal|El Universal|eluniversal.com.mx|MX|Latin America|center|0|general|world,politics,culture|Mexico's oldest daily.
cnbc|CNBC|cnbc.com|US|United States|center|0|general|business,money,tech,politics|Markets and money, all day.
bloomberg|Bloomberg|bloomberg.com|US|United States|center|1|general|business,money,tech,world|Global financial news powerhouse.
marketwatch|MarketWatch|marketwatch.com|US|United States|center|0|general|money,business|Markets news for everyday investors.
fortune|Fortune|fortune.com|US|United States|center|0|general|business,money,tech,politics|Business magazine with executive interviews.
forbes|Forbes|forbes.com|US|United States|center-right|0|general|business,money,tech|Business, wealth and entrepreneurship.
barrons|Barron's|barrons.com|US|United States|center|1|general|money,business|Investing weekly.
businessinsider|Business Insider|businessinsider.com|US|United States|center|0|student|business,money,tech,culture|Fast business and tech explainers.
fastcompany|Fast Company|fastcompany.com|US|United States|center-left|0|student|business,tech,culture|Innovation and workplace culture.
techcrunch|TechCrunch|techcrunch.com|US|United States|center|0|general|tech,business|Startup and venture news.
verge|The Verge|theverge.com|US|United States|center|0|teen|tech,science,culture,gaming|Gadgets and internet culture with personality.
arstechnica|Ars Technica|arstechnica.com|US|United States|center|0|student|tech,science,space,politics|Technical depth without the hype.
wired|WIRED|wired.com|US|United States|center-left|1|student|tech,science,culture,business|Technology and its effect on everything.
engadget|Engadget|engadget.com|US|United States|center|0|teen|tech,gaming|Consumer tech reviews and news.
gizmodo|Gizmodo|gizmodo.com|US|United States|center|0|teen|tech,science,culture|Tech news with a sense of humour.
venturebeat|VentureBeat|venturebeat.com|US|United States|center|0|general|tech,business|Enterprise tech and AI news.
mittr|MIT Technology Review|technologyreview.com|US|Global|center|1|student|tech,science,climate|Emerging tech, explained by MIT.
toms|Tom's Hardware|tomshardware.com|US|Global|center|0|student|tech,gaming|PC hardware reviews and benchmarks.
theregister|The Register|theregister.com|GB|United Kingdom|center|0|student|tech,business|Irreverent enterprise IT news.
media404|404 Media|404media.co|US|United States|center-left|0|student|tech,culture|Journalist-owned tech accountability.
restofworld|Rest of World|restofworld.org|US|Global|center|0|student|tech,world,business|Tech outside the Western bubble.
spectrum|IEEE Spectrum|spectrum.ieee.org|US|Global|center|0|student|tech,science|Engineering breakthroughs.
zdnet|ZDNET|zdnet.com|US|Global|center|0|general|tech,business|Enterprise and consumer tech.
cnet|CNET|cnet.com|US|United States|center|0|teen|tech,money|Reviews and how-tos.
androidauthority|Android Authority|androidauthority.com|US|Global|center|0|teen|tech|Android news and reviews.
ninetofivemac|9to5Mac|9to5mac.com|US|Global|center|0|teen|tech|Apple news and rumours.
macrumors|MacRumors|macrumors.com|US|Global|center|0|teen|tech|Apple news aggregation and forums.
bleepingcomputer|BleepingComputer|bleepingcomputer.com|US|Global|center|0|student|tech|Security and malware news.
hackernews|Hacker News|news.ycombinator.com|US|Global|center|0|specialist|tech,business|Community-ranked tech and startup links.
eurogamer|Eurogamer|eurogamer.net|GB|United Kingdom|center|0|teen|gaming,tech|Games reviews and industry news.
rockpapershotgun|Rock Paper Shotgun|rockpapershotgun.com|GB|United Kingdom|center|0|teen|gaming,tech|PC gaming with wit.
gamespot|GameSpot|gamespot.com|US|United States|center|0|teen|gaming,tech|Games news, reviews and trailers.
pcgamesn|PCGamesN|pcgamesn.com|GB|United Kingdom|center|0|teen|gaming|PC gaming news.
nintendolife|Nintendo Life|nintendolife.com|GB|United Kingdom|center|0|teen|gaming|Nintendo news and reviews.
pushsquare|Push Square|pushsquare.com|GB|United Kingdom|center|0|teen|gaming|PlayStation news.
gamesindustry|GamesIndustry.biz|gamesindustry.biz|GB|Global|center|0|student|gaming,business|The business of video games.
vg247|VG247|vg247.com|GB|United Kingdom|center|0|teen|gaming|Games news and deals.
dexerto|Dexerto|dexerto.com|GB|Global|center|0|teen|gaming,entertainment|Gaming and creator culture.
dotesports|Dot Esports|dotesports.com|US|Global|center|0|teen|gaming,sports|Esports news and results.
polygon|Polygon|polygon.com|US|United States|center|0|teen|gaming,entertainment,culture|Games and pop culture.
ign|IGN|ign.com|US|Global|center|0|teen|gaming,entertainment,tech|Games, movies and TV.
kotaku|Kotaku|kotaku.com|US|United States|center-left|0|teen|gaming,culture|Games culture and industry.
pcgamer|PC Gamer|pcgamer.com|GB|Global|center|0|teen|gaming,tech|PC gaming magazine.
espn|ESPN|espn.com|US|United States|center|0|general|sports|Live scores, highlights and sports news.
cbssports|CBS Sports|cbssports.com|US|United States|center|0|general|sports|US sports news and analysis.
yahoosports|Yahoo Sports|sports.yahoo.com|US|United States|center|0|general|sports|Scores, fantasy and news.
bleacherreport|Bleacher Report|bleacherreport.com|US|United States|center|0|teen|sports|Fan-first sports coverage and highlights.
theathletic|The Athletic|theathletic.com|US|United States|center|1|general|sports|Deep sports reporting, subscription based.
espncricinfo|ESPNcricinfo|espncricinfo.com|IN|Global|center|0|specialist|sports|The home of cricket.
skysports|Sky Sports|skysports.com|GB|United Kingdom|center|0|general|sports|UK sports news and live coverage.
motorsport|Motorsport.com|motorsport.com|US|Global|center|0|specialist|sports|F1, MotoGP and racing news.
autosport|Autosport|autosport.com|GB|Global|center|1|specialist|sports|Motor racing journalism since 1950.
cyclingnews|Cyclingnews|cyclingnews.com|GB|Global|center|0|specialist|sports|Pro cycling news and results.
golfdigest|Golf Digest|golfdigest.com|US|Global|center|0|specialist|sports|Golf news, instruction and gear.
mmafighting|MMA Fighting|mmafighting.com|US|Global|center|0|specialist|sports|MMA and UFC coverage.
goal|Goal|goal.com|GB|Global|center|0|teen|sports|Global football news.
fourfourtwo|FourFourTwo|fourfourtwo.com|GB|Global|center|0|teen|sports|Football features and analysis.
talksport|talkSPORT|talksport.com|GB|United Kingdom|center|0|general|sports|UK sports radio and news.
tenniscom|Tennis.com|tennis.com|US|Global|center|0|specialist|sports|Tennis news and instruction.
variety|Variety|variety.com|US|United States|center|0|general|entertainment,business|The entertainment industry's trade paper.
thr|The Hollywood Reporter|hollywoodreporter.com|US|United States|center|0|general|entertainment|Film, TV and awards coverage.
billboard|Billboard|billboard.com|US|United States|center|0|teen|music,entertainment|Charts, music news and industry.
rollingstone|Rolling Stone|rollingstone.com|US|United States|left|0|teen|music,culture,entertainment,politics|Music, politics and culture since 1967.
pitchfork|Pitchfork|pitchfork.com|US|United States|center|0|teen|music,culture|Album reviews and music news.
consequence|Consequence|consequence.net|US|United States|center|0|teen|music,entertainment|Music and pop culture.
nme|NME|nme.com|GB|United Kingdom|center|0|teen|music,entertainment|British music magazine.
stereogum|Stereogum|stereogum.com|US|United States|center|0|teen|music|Indie and alternative music.
spin|SPIN|spin.com|US|United States|center|0|teen|music|Music magazine.
brooklynvegan|BrooklynVegan|brooklynvegan.com|US|United States|center|0|teen|music|Music news and live listings.
xxlmag|XXL|xxlmag.com|US|United States|center|0|teen|music|Hip-hop news.
complex|Complex|complex.com|US|United States|center|0|teen|music,culture|Music, sneakers and youth culture.
hypebeast|Hypebeast|hypebeast.com|HK|Global|center|0|teen|culture,entertainment|Streetwear and pop culture.
deadline|Deadline|deadline.com|US|United States|center|0|general|entertainment,business|Hollywood business news.
indiewire|IndieWire|indiewire.com|US|United States|center|0|general|entertainment|Film and TV for cinephiles.
thewrap|TheWrap|thewrap.com|US|United States|center|0|general|entertainment|Entertainment business and awards.
screenrant|Screen Rant|screenrant.com|CA|United States|center|0|teen|entertainment|Movies, TV and lists.
collider|Collider|collider.com|US|United States|center|0|teen|entertainment|Film and TV news.
vulture|Vulture|vulture.com|US|United States|center|0|teen|entertainment,culture|Sharp culture criticism.
avclub|The A.V. Club|avclub.com|US|United States|center-left|0|teen|entertainment,culture|Pop culture reviews.
digitalspy|Digital Spy|digitalspy.com|GB|United Kingdom|center|0|teen|entertainment|TV and celebrity news.
empire|Empire|empireonline.com|GB|United Kingdom|center|0|teen|entertainment|Film magazine.
tvline|TVLine|tvline.com|US|United States|center|0|teen|entertainment|TV news and ratings.
decider|Decider|decider.com|US|United States|center|0|teen|entertainment|What to watch.
slashfilm|/Film|slashfilm.com|US|United States|center|0|teen|entertainment|Film news and analysis.
artnews|ARTnews|artnews.com|US|Global|center|0|student|culture|Art world news since 1902.
artnet|Artnet News|news.artnet.com|US|Global|center|0|student|culture|Art market and museum news.
theartnewspaper|The Art Newspaper|theartnewspaper.com|GB|Global|center|0|student|culture|International art journalism.
hyperallergic|Hyperallergic|hyperallergic.com|US|Global|center-left|0|student|culture|Art criticism and news.
lithub|Literary Hub|lithub.com|US|Global|center|0|student|culture|Books and literary culture.
kirkus|Kirkus Reviews|kirkusreviews.com|US|Global|center|0|student|culture|Book reviews and discovery.
electricliterature|Electric Literature|electricliterature.com|US|Global|center|0|student|culture|Independent literary magazine.
openculture|Open Culture|openculture.com|US|Global|center|0|student|culture,education|Free cultural and educational media.
marginalian|The Marginalian|themarginalian.org|US|Global|center|0|student|culture|Maria Popova on art, science and philosophy.
eater|Eater|eater.com|US|United States|center|0|teen|food,culture|Food and restaurant culture.
seriouseats|Serious Eats|seriouseats.com|US|United States|center|0|teen|food|Tested recipes and food science.
bonappetit|Bon Appétit|bonappetit.com|US|United States|center|0|teen|food|Recipes and food culture.
food52|Food52|food52.com|US|United States|center|0|teen|food|Home cooking community.
thekitchn|The Kitchn|thekitchn.com|US|United States|center|0|teen|food|Kitchen tips and recipes.
delish|Delish|delish.com|US|United States|center|0|teen|food|Fun, fast recipes.
saveur|Saveur|saveur.com|US|Global|center|0|teen|food,travel|Culinary travel.
epicurious|Epicurious|epicurious.com|US|United States|center|0|teen|food|Recipes and technique.
cntraveler|Condé Nast Traveler|cntraveler.com|US|Global|center|0|teen|travel,culture|Luxury and destination travel.
travelandleisure|Travel + Leisure|travelandleisure.com|US|Global|center|0|teen|travel|Destinations, hotels and tips.
lonelyplanet|Lonely Planet|lonelyplanet.com|GB|Global|center|0|teen|travel|Guidebook publisher's travel news.
skift|Skift|skift.com|US|Global|center|0|specialist|travel,business|Travel industry intelligence.
roadsandkingdoms|Roads & Kingdoms|roadsandkingdoms.com|US|Global|center|0|teen|food,travel|Food and travel storytelling.
carbonbrief|Carbon Brief|carbonbrief.org|GB|Global|center|0|specialist|climate,science,politics|Climate science and policy analysis.
grist|Grist|grist.org|US|United States|center-left|0|student|climate,politics|Climate solutions journalism.
insideclimate|Inside Climate News|insideclimatenews.org|US|United States|center|0|student|climate,politics|Non-profit climate investigations.
yaleclimate|Yale Climate Connections|yaleclimateconnections.org|US|United States|center|0|student|climate,science|Climate explained, without the doom.
climatehome|Climate Home News|climatechangenews.com|GB|Global|center|0|specialist|climate,politics|International climate politics.
pew|Pew Research Center|pewresearch.org|US|Global|center|0|student|politics,us,world,tech,education,health|Data on how people live and think.
brookings|Brookings Institution|brookings.edu|US|Global|center|0|student|politics,world,business,education,climate|Policy research and analysis.
cfr|Council on Foreign Relations|cfr.org|US|Global|center|0|student|politics,world|Foreign policy analysis and explainers.
foreignpolicy|Foreign Policy|foreignpolicy.com|US|Global|center|1|student|politics,world,business|Global affairs magazine.
foreignaffairs|Foreign Affairs|foreignaffairs.com|US|Global|center|1|student|politics,world|The long-form foreign policy journal.
cjr|Columbia Journalism Review|cjr.org|US|Global|center-left|0|student|education,opinion,culture|Media criticism and industry news.
niemanlab|Nieman Lab|niemanlab.org|US|Global|center-left|0|student|education,tech,opinion|The future of journalism.
globalvoices|Global Voices|globalvoices.org|INT|Global|center|0|student|world,culture|Citizen media from around the world.
theconversation|The Conversation|theconversation.com|AU|Global|center|0|student|science,health,politics,education,climate,tech,culture|Academics writing for the public, with disclosure.
dazed|Dazed|dazeddigital.com|GB|United Kingdom|center-left|0|teen|culture,music,entertainment|Youth culture, fashion and identity.
them|Them|them.us|US|United States|left|0|teen|culture,politics,health|LGBTQ+ news and culture.
refinery29|Refinery29|refinery29.com|US|United States|left|0|teen|culture,money,health|Style, money and life for young women.
mashable|Mashable|mashable.com|US|United States|center|0|teen|tech,culture,entertainment|Digital culture and tech for the extremely online.
buzzfeed|BuzzFeed|buzzfeed.com|US|United States|left|0|teen|culture,entertainment|Internet culture, quizzes and news.
studyinternational|Study International|studyinternational.com|GB|Global|center|0|student|education,travel|Study-abroad and university news for international students.
universityworldnews|University World News|universityworldnews.com|GB|Global|center|0|student|education,politics|Global higher-education journalism.
timeshighereducation|Times Higher Education|timeshighereducation.com|GB|Global|center|1|student|education|University rankings, policy and academic life.
"""

# ---------------------------------------------------------------------------
# Feeds: source_id | topic hint | url
# A publication can contribute many feeds; the topic hint only guides
# classification, it never overrides what an article is actually about.
# `espn-json:<league>` pulls ESPN's public news JSON for that competition.
#
# NOTE: the catalog is intentionally complete. A feed that is blocked on one
# network (school/office/parental filters) still belongs here: the ingester
# records it as "unreachable from this network" and keeps retrying, so the app
# works everywhere else without dropping sources.
# ---------------------------------------------------------------------------
FEEDS_RAW = """\
bbc|world|https://feeds.bbci.co.uk/news/world/rss.xml
bbc|world|https://feeds.bbci.co.uk/news/uk/rss.xml
bbc|business|https://feeds.bbci.co.uk/news/business/rss.xml
bbc|tech|https://feeds.bbci.co.uk/news/technology/rss.xml
bbc|science|https://feeds.bbci.co.uk/news/science_and_environment/rss.xml
bbc|health|https://feeds.bbci.co.uk/news/health/rss.xml
bbc|sports|https://feeds.bbci.co.uk/sport/rss.xml
bbc|sports|https://feeds.bbci.co.uk/sport/football/rss.xml
bbc|education|https://feeds.bbci.co.uk/news/education/rss.xml
bbc|entertainment|https://feeds.bbci.co.uk/news/entertainment_and_arts/rss.xml
ap|world|https://apnews.com/hub/ap-top-news?output=rss
ap|world|https://apnews.com/hub/world-news?output=rss
ap|politics|https://apnews.com/hub/politics?output=rss
ap|sports|https://apnews.com/hub/sports?output=rss
reuters|world|https://www.reutersagency.com/feed/?best-topics=world&post_type=best
reuters|tech|https://www.reutersagency.com/feed/?best-topics=tech&post_type=best
reuters|business|https://www.reutersagency.com/feed/?best-topics=business-finance&post_type=best
aljazeera|world|https://www.aljazeera.com/xml/rss/all.xml
dw|world|https://rss.dw.com/rdf/rss-en-world
dw|world|https://rss.dw.com/rdf/rss-en-eu
dw|world|https://rss.dw.com/rdf/rss-en-all
france24|world|https://www.france24.com/en/rss
euronews|world|https://www.euronews.com/rss?level=theme&name=news
unnews|world|https://news.un.org/feed/subscribe/en/news/all/rss.xml
who|health|https://www.who.int/rss-feeds/news-english.xml
nature|science|https://www.nature.com/nature.rss
science|science|https://www.science.org/rss/news_current.xml
sciencedaily|science|https://www.sciencedaily.com/rss/all.xml
phys|science|https://phys.org/rss-feed/
quanta|science|https://www.quantamagazine.org/feed/
scientificamerican|science|https://www.scientificamerican.com/feed/
newscientist|science|https://www.newscientist.com/feed/home/
nautilus|science|https://nautil.us/feed/
aeon|science|https://aeon.co/feed.rss
smithsonian|culture|https://www.smithsonianmag.com/rss/latest_articles/
atlasobscura|travel|https://www.atlasobscura.com/feeds/latest
natgeo|science|https://www.nationalgeographic.com/feed
spacecom|space|https://www.space.com/feeds/all
livescience|science|https://www.livescience.com/feeds/all
universetoday|space|https://www.universetoday.com/feed/
nasa|space|https://www.nasa.gov/feed/
esa|space|https://www.esa.int/rssfeed/Our_Activities/Space_News
noaa|climate|https://www.noaa.gov/news/rss
worldbank|business|https://www.worldbank.org/en/news/all?format=rss
govuk|politics|https://www.gov.uk/search/news-and-communications.atom
eucommission|politics|https://ec.europa.eu/commission/presscorner/api/rss?language=en
nyt|world|https://rss.nytimes.com/services/xml/rss/nyt/World.xml
nyt|us|https://rss.nytimes.com/services/xml/rss/nyt/US.xml
nyt|us|https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml
nyt|business|https://rss.nytimes.com/services/xml/rss/nyt/Business.xml
nyt|tech|https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml
nyt|science|https://rss.nytimes.com/services/xml/rss/nyt/Science.xml
nyt|sports|https://rss.nytimes.com/services/xml/rss/nyt/Sports.xml
nyt|entertainment|https://rss.nytimes.com/services/xml/rss/nyt/Arts.xml
nyt|health|https://rss.nytimes.com/services/xml/rss/nyt/Health.xml
nyt|climate|https://rss.nytimes.com/services/xml/rss/nyt/Climate.xml
nyt|education|https://rss.nytimes.com/services/xml/rss/nyt/Education.xml
nyt|politics|https://rss.nytimes.com/services/xml/rss/nyt/Politics.xml
nyt|travel|https://rss.nytimes.com/services/xml/rss/nyt/Travel.xml
nyt|food|https://rss.nytimes.com/services/xml/rss/nyt/DiningandWine.xml
nyt|entertainment|https://rss.nytimes.com/services/xml/rss/nyt/Movies.xml
nyt|music|https://rss.nytimes.com/services/xml/rss/nyt/Music.xml
nyt|culture|https://rss.nytimes.com/services/xml/rss/nyt/Books.xml
nyt|money|https://rss.nytimes.com/services/xml/rss/nyt/YourMoney.xml
wapo|world|https://feeds.washingtonpost.com/rss/world
wapo|us|https://feeds.washingtonpost.com/rss/national
wapo|politics|https://feeds.washingtonpost.com/rss/politics
wapo|business|https://feeds.washingtonpost.com/rss/business
wapo|tech|https://feeds.washingtonpost.com/rss/business/technology
wapo|sports|https://feeds.washingtonpost.com/rss/sports
wapo|entertainment|https://feeds.washingtonpost.com/rss/entertainment
wapo|health|https://feeds.washingtonpost.com/rss/health
wapo|climate|https://feeds.washingtonpost.com/rss/climate-environment
wsj|world|https://feeds.a.dj.com/rss/RSSWorldNews.xml
wsj|tech|https://feeds.a.dj.com/rss/RSSWSJD.xml
wsj|us|https://feeds.a.dj.com/rss/RSSUSNews.xml
wsj|opinion|https://feeds.a.dj.com/rss/RSSOpinion.xml
wsj|business|https://feeds.a.dj.com/rss/WSJcomUSBusiness.xml
wsj|money|https://feeds.a.dj.com/rss/RSSMarketsMain.xml
cnn|world|http://rss.cnn.com/rss/cnn_topstories.rss
cnn|world|http://rss.cnn.com/rss/cnn_world.rss
cnn|tech|http://rss.cnn.com/rss/cnn_tech.rss
cnn|politics|http://rss.cnn.com/rss/cnn_allpolitics.rss
cnn|health|http://rss.cnn.com/rss/cnn_health.rss
cnn|entertainment|http://rss.cnn.com/rss/cnn_showbiz.rss
npr|us|https://feeds.npr.org/1001/rss.xml
npr|world|https://feeds.npr.org/1004/rss.xml
npr|business|https://feeds.npr.org/1006/rss.xml
npr|tech|https://feeds.npr.org/1019/rss.xml
npr|science|https://feeds.npr.org/1025/rss.xml
npr|sports|https://feeds.npr.org/1055/rss.xml
npr|entertainment|https://feeds.npr.org/1008/rss.xml
pbs|us|https://www.pbs.org/newshour/feeds/rss/headlines
pbs|world|https://www.pbs.org/newshour/feeds/rss/world
usatoday|us|https://rssfeeds.usatoday.com/usatoday-NewsTopStories
usatoday|sports|https://rssfeeds.usatoday.com/UsatodaycomSports-TopStories
nbc|us|https://feeds.nbcnews.com/nbcnews/public/news
nbc|world|https://feeds.nbcnews.com/nbcnews/public/world
abcnews|us|https://abcnews.go.com/abcnews/topstories
abcnews|world|https://abcnews.go.com/abcnews/internationalnews
cbsnews|us|https://www.cbsnews.com/latest/rss/main
cbsnews|world|https://www.cbsnews.com/latest/rss/world
foxnews|us|https://moxie.foxnews.com/google-publisher/latest.xml
foxnews|politics|https://moxie.foxnews.com/google-publisher/politics.xml
foxnews|sports|https://moxie.foxnews.com/google-publisher/sports.xml
nypost|us|https://nypost.com/feed/
nypost|entertainment|https://nypost.com/entertainment/feed/
latimes|us|https://www.latimes.com/rss2.0.xml
latimes|sports|https://www.latimes.com/sports/rss2.0.xml
latimes|world|https://www.latimes.com/world/rss2.0.xml
latimes|entertainment|https://www.latimes.com/entertainment-arts/rss2.0.xml
politico|politics|https://www.politico.com/rss/politicopicks.xml
politico|world|https://www.politico.com/rss/foreignpolicy.xml
thehill|politics|https://thehill.com/feed/
axios|politics|https://api.axios.com/feed/
propublica|us|https://www.propublica.org/feeds/propublica/main
motherjones|politics|https://www.motherjones.com/feed/
reason|politics|https://reason.com/feed/
nationalreview|politics|https://www.nationalreview.com/feed/
vox|politics|https://www.vox.com/rss/index.xml
slate|culture|https://slate.com/feeds/all.rss
salon|politics|https://www.salon.com/feed/
thedailybeast|politics|https://feeds.thedailybeast.com/summary/rss
huffpost|politics|https://www.huffpost.com/section/front-page/feed
theintercept|politics|https://theintercept.com/feed/?lang=en
thenation|politics|https://www.thenation.com/feed/?post_type=article
newsweek|world|https://www.newsweek.com/rss
csmonitor|world|https://rss.csmonitor.com/feeds/top
statnews|health|https://www.statnews.com/feed/
kff|health|https://kffhealthnews.org/feed/
harvardhealth|health|https://www.health.harvard.edu/blog/feed
insidehighered|education|https://www.insidehighered.com/rss.xml
edsurge|education|https://www.edsurge.com/rss
hechinger|education|https://hechingerreport.org/feed/
the74|education|https://www.the74million.org/feed/
chalkbeat|education|https://www.chalkbeat.org/arc/outboundfeeds/rss/?outputType=xml
teenvogue|culture|https://www.teenvogue.com/feed/rss
seventeen|culture|https://www.seventeen.com/rss/
guardian|world|https://www.theguardian.com/world/rss
guardian|us|https://www.theguardian.com/us-news/rss
guardian|politics|https://www.theguardian.com/us/politics/rss
guardian|tech|https://www.theguardian.com/uk/technology/rss
guardian|science|https://www.theguardian.com/science/rss
guardian|sports|https://www.theguardian.com/uk/sport/rss
guardian|culture|https://www.theguardian.com/culture/rss
guardian|climate|https://www.theguardian.com/environment/rss
guardian|education|https://www.theguardian.com/education/rss
guardian|business|https://www.theguardian.com/uk/business/rss
guardian|food|https://www.theguardian.com/food/rss
guardian|travel|https://www.theguardian.com/travel/rss
independent|world|https://www.independent.co.uk/news/rss
independent|sports|https://www.independent.co.uk/sport/rss
independent|tech|https://www.independent.co.uk/tech/rss
telegraph|world|https://www.telegraph.co.uk/news/rss.xml
telegraph|sports|https://www.telegraph.co.uk/sport/rss.xml
ft|world|https://www.ft.com/rss/home
economist|world|https://www.economist.com/latest/rss.xml
economist|business|https://www.economist.com/business/rss.xml
economist|money|https://www.economist.com/finance-and-economics/rss.xml
economist|science|https://www.economist.com/science-and-technology/rss.xml
economist|culture|https://www.economist.com/culture/rss.xml
economist|politics|https://www.economist.com/leaders/rss.xml
skynews|world|https://feeds.skynews.com/feeds/rss/home.xml
skynews|sports|https://feeds.skynews.com/feeds/rss/sports.xml
mirror|entertainment|https://www.mirror.co.uk/news/?service=rss
express|world|https://www.express.co.uk/posts/rss/1/news
dailymail|world|https://www.dailymail.co.uk/news/index.rss
metro|entertainment|https://metro.co.uk/feed/
standard|world|https://www.standard.co.uk/rss
scotsman|world|https://www.scotsman.com/rss
rte|world|https://www.rte.ie/feeds/rss/?index=/news/
rte|sports|https://www.rte.ie/feeds/rss/?index=/sport/
irishtimes|world|https://www.irishtimes.com/arc/outboundfeeds/rss/?outputType=xml
the42|sports|https://www.the42.ie/feed/
spiegel|world|https://www.spiegel.de/international/index.rss
zeit|world|https://www.zeit.de/news/index
faz|world|https://www.faz.net/rss/aktuell/
sueddeutsche|world|https://rss.sueddeutsche.de/rss/Topthemen
lemonde|world|https://www.lemonde.fr/en/rss/une.xml
lefigaro|world|https://www.lefigaro.fr/rss/figaro_actualites.xml
liberation|world|https://www.liberation.fr/arc/outboundfeeds/rss/?outputType=xml
elpais|world|https://feeds.elpais.com/mrss-s/pages/ep/site/english.elpais.com/portada
elmundo|world|https://www.elmundo.es/rss/portada.xml
ansa|world|https://www.ansa.it/sito/ansait_rss.xml
corriere|world|https://xml2.corriereobjects.it/rss/homepage.xml
repubblica|world|https://www.repubblica.it/rss/homepage/rss2.0.xml
dutchnews|world|https://www.dutchnews.nl/feed/
thelocalde|world|https://www.thelocal.de/feed/rss
swissinfo|world|https://www.swissinfo.ch/eng/rss
euobserver|politics|https://euobserver.com/rss
politicoeu|politics|https://www.politico.eu/feed/
kyivindependent|world|https://kyivindependent.com/feed/
moscowtimes|world|https://www.themoscowtimes.com/rss/news
timesofisrael|world|https://www.timesofisrael.com/feed/
jpost|world|https://www.jpost.com/rss/rssfeedsfrontpage.aspx
haaretz|world|https://www.haaretz.com/cmlink/1.628752
972mag|politics|https://972mag.com/feed/
arabnews|world|https://www.arabnews.com/rss.xml
gulfnews|world|https://gulfnews.com/feed
khaleejtimes|world|https://www.khaleejtimes.com/rss
thenational|world|https://www.thenationalnews.com/arc/outboundfeeds/rss/?outputType=xml
middleeasteye|world|https://www.middleeasteye.net/rss
tehrantimes|world|https://www.tehrantimes.com/rss
hurriyet|world|https://www.hurriyetdailynews.com/rss
dailysabah|world|https://www.dailysabah.com/rss/news
dailysabah|world|https://www.dailysabah.com/rss/world
punch|world|https://punchng.com/feed/
premiumtimes|politics|https://www.premiumtimesng.com/feed
vanguardngr|politics|https://www.vanguardngr.com/feed/
myjoyonline|world|https://www.myjoyonline.com/feed/
mg|world|https://mg.co.za/feed/
dailymaverick|politics|https://www.dailymaverick.co.za/feed/
news24|world|https://feeds.24.com/articles/news24/TopStories/rss
eastafrican|world|https://www.theeastafrican.co.ke/tea/rss
nationafrica|world|https://nation.africa/kenya/rss
ahram|world|https://english.ahram.org.eg/rss.aspx
moroccoworldnews|world|https://www.moroccoworldnews.com/feed/
toi|world|https://timesofindia.indiatimes.com/rssfeedstopstories.cms
toi|world|https://timesofindia.indiatimes.com/rssfeeds/-2128936835.cms
toi|sports|https://timesofindia.indiatimes.com/rssfeeds/4719148.cms
toi|entertainment|https://timesofindia.indiatimes.com/rssfeeds/1081479906.cms
hindu|world|https://www.thehindu.com/news/national/feeder/default.rss
hindu|sports|https://www.thehindu.com/sport/feeder/default.rss
hindu|science|https://www.thehindu.com/sci-tech/feeder/default.rss
hindu|education|https://www.thehindu.com/education/feeder/default.rss
ndtv|world|https://feeds.feedburner.com/ndtvnews-top-stories
ndtv|world|https://feeds.feedburner.com/ndtvnews-india-news
ndtv|sports|https://feeds.feedburner.com/ndtvnews-sports-news
indianexpress|world|https://indianexpress.com/feed/
hindustantimes|world|https://www.hindustantimes.com/feeds/rss/india-news/rssfeed.xml
hindustantimes|entertainment|https://www.hindustantimes.com/feeds/rss/entertainment/rssfeed.xml
scroll|culture|https://scroll.in/feed
thewire|politics|https://thewire.in/rss
livemint|business|https://www.livemint.com/rss/news
firstpost|world|https://www.firstpost.com/rss/india.xml
dawn|world|https://www.dawn.com/feeds/home
tribune|world|https://tribune.com.pk/feed/home
kathmandupost|world|https://kathmandupost.com/rss
dailystar|world|https://www.thedailystar.net/frontpage/rss.xml
dailymirror|world|https://www.dailymirror.lk/RSS_Feeds/breaking-news
japantimes|world|https://www.japantimes.co.jp/feed/
nhk|world|https://www3.nhk.or.jp/rss/news/cat0.xml
asahi|world|https://www.asahi.com/rss/asahi/newsheadlines.rdf
nikkei|business|https://asia.nikkei.com/rss/feed/nar
koreaherald|world|https://www.koreaherald.com/rss/
yonhap|world|https://en.yna.co.kr/RSS/news.xml
scmp|world|https://www.scmp.com/rss/91/feed
hkfp|politics|https://hongkongfp.com/feed/
taipeitimes|world|https://www.taipeitimes.com/xml/index.rss
straitstimes|world|https://www.straitstimes.com/news/world/rss.xml
straitstimes|world|https://www.straitstimes.com/news/singapore/rss.xml
cna|world|https://www.channelnewsasia.com/api/v1/rss-outbound-feed?_format=xml
jakartapost|world|https://www.thejakartapost.com/rss
bangkokpost|world|https://www.bangkokpost.com/rss/data/topstories.xml
vnexpress|world|https://e.vnexpress.net/rss/news.rss
inquirer|world|https://newsinfo.inquirer.net/feed
rappler|politics|https://www.rappler.com/feed/
abcau|world|https://www.abc.net.au/news/feed/51120/rss.xml
abcau|world|https://www.abc.net.au/news/feed/45924/rss.xml
smh|world|https://www.smh.com.au/rss/feed.xml
theage|world|https://www.theage.com.au/rss/feed.xml
guardianau|world|https://www.theguardian.com/au/rss
sbs|world|https://www.sbs.com.au/news/feed
nzherald|world|https://www.nzherald.co.nz/arc/outboundfeeds/rss/
rnz|world|https://www.rnz.co.nz/rss/national.xml
cbc|world|https://www.cbc.ca/webfeed/rss/rss-topstories
cbc|world|https://www.cbc.ca/webfeed/rss/rss-world
cbc|tech|https://www.cbc.ca/webfeed/rss/rss-technology
cbc|health|https://www.cbc.ca/webfeed/rss/rss-health
cbc|sports|https://www.cbc.ca/webfeed/rss/rss-sports
globeandmail|world|https://www.theglobeandmail.com/arc/outboundfeeds/rss/category/canada/?outputType=xml
nationalpost|world|https://nationalpost.com/feed/
ctvnews|world|https://www.ctvnews.ca/rss/ctvnews-ca-top-stories-public-rss-1.822009
infobae|world|https://www.infobae.com/arc/outboundfeeds/rss/?outputType=xml
clarin|world|https://www.clarin.com/rss/lo-ultimo/
folha|world|https://feeds.folha.uol.com.br/emcimadahora/rss091.xml
eluniversal|world|https://www.eluniversal.com.mx/rss.xml
cnbc|business|https://www.cnbc.com/id/100003114/device/rss/rss.html
cnbc|tech|https://www.cnbc.com/id/19854910/device/rss/rss.html
bloomberg|money|https://feeds.bloomberg.com/markets/news.rss
marketwatch|money|https://feeds.content.dowjones.io/public/rss/mw_topstories
fortune|business|https://fortune.com/feed/
forbes|business|https://www.forbes.com/business/feed/
barrons|money|https://feeds.a.dj.com/rss/RSSBarrons.xml
businessinsider|business|https://www.businessinsider.com/rss
fastcompany|business|https://www.fastcompany.com/rss
techcrunch|tech|https://techcrunch.com/feed/
verge|tech|https://www.theverge.com/rss/index.xml
verge|tech|https://www.theverge.com/rss/tech/index.xml
arstechnica|tech|https://feeds.arstechnica.com/arstechnica/index
wired|tech|https://www.wired.com/feed/rss
engadget|tech|https://www.engadget.com/rss.xml
gizmodo|tech|https://gizmodo.com/rss
venturebeat|tech|https://venturebeat.com/feed/
mittr|tech|https://www.technologyreview.com/feed/
toms|tech|https://www.tomshardware.com/feeds/all
theregister|tech|https://www.theregister.com/headlines.atom
media404|tech|https://www.404media.co/rss/
restofworld|tech|https://restofworld.org/feed/latest
spectrum|tech|https://spectrum.ieee.org/feeds/feed.rss
zdnet|tech|https://www.zdnet.com/news/rss.xml
cnet|tech|https://www.cnet.com/rss/news/
androidauthority|tech|https://www.androidauthority.com/feed/
ninetofivemac|tech|https://9to5mac.com/feed/
macrumors|tech|https://www.macrumors.com/macrumors.xml
bleepingcomputer|tech|https://www.bleepingcomputer.com/feed/
hackernews|tech|https://hnrss.org/frontpage
eurogamer|gaming|https://www.eurogamer.net/feed
rockpapershotgun|gaming|https://www.rockpapershotgun.com/feed
gamespot|gaming|https://www.gamespot.com/feeds/mashup/
pcgamesn|gaming|https://www.pcgamesn.com/rss
nintendolife|gaming|https://www.nintendolife.com/feeds/latest
pushsquare|gaming|https://www.pushsquare.com/feeds/latest
gamesindustry|gaming|https://www.gamesindustry.biz/feed
vg247|gaming|https://www.vg247.com/feed
dexerto|gaming|https://www.dexerto.com/feed/
dotesports|gaming|https://dotesports.com/feed
polygon|gaming|https://www.polygon.com/rss/index.xml
ign|gaming|https://feeds.ign.com/ign/all
kotaku|gaming|https://kotaku.com/rss
pcgamer|gaming|https://www.pcgamer.com/rss
espn|sports|espn-json:nba
espn|sports|espn-json:nfl
espn|sports|espn-json:mlb
espn|sports|espn-json:nhl
espn|sports|espn-json:wnba
espn|sports|espn-json:mls
espn|sports|espn-json:eng.1
espn|sports|espn-json:esp.1
espn|sports|espn-json:uefa.champions
espn|sports|espn-json:ncaaf
espn|sports|espn-json:ncaab
espn|sports|espn-json:f1
cbssports|sports|https://www.cbssports.com/rss/headlines/
yahoosports|sports|https://sports.yahoo.com/rss/
bleacherreport|sports|https://bleacherreport.com/articles/feed
theathletic|sports|https://theathletic.com/feed/
espncricinfo|sports|https://www.espncricinfo.com/rss/content/story/feeds/0.xml
skysports|sports|https://www.skysports.com/rss/12040
skysports|sports|https://www.skysports.com/rss/12433
motorsport|sports|https://www.motorsport.com/rss/all/news/
autosport|sports|https://www.autosport.com/rss/all/news
cyclingnews|sports|https://www.cyclingnews.com/feeds/all
golfdigest|sports|https://www.golfdigest.com/feed/rss
mmafighting|sports|https://www.mmafighting.com/rss/current
goal|sports|https://www.goal.com/feeds/en/news
fourfourtwo|sports|https://www.fourfourtwo.com/feeds/all
talksport|sports|https://talksport.com/feed/
tenniscom|sports|https://www.tennis.com/rss
variety|entertainment|https://variety.com/feed/
thr|entertainment|https://www.hollywoodreporter.com/feed/
billboard|music|https://www.billboard.com/feed/
rollingstone|music|https://www.rollingstone.com/feed/
pitchfork|music|https://pitchfork.com/feed/feed-news/rss
consequence|music|https://consequence.net/feed/
nme|music|https://www.nme.com/feed
stereogum|music|https://www.stereogum.com/feed/
spin|music|https://www.spin.com/feed/
brooklynvegan|music|https://www.brooklynvegan.com/feed/
xxlmag|music|https://www.xxlmag.com/feed/
complex|music|https://www.complex.com/rss
hypebeast|culture|https://hypebeast.com/feed
deadline|entertainment|https://deadline.com/feed/
indiewire|entertainment|https://www.indiewire.com/feed/
thewrap|entertainment|https://www.thewrap.com/feed/
screenrant|entertainment|https://screenrant.com/feed/
collider|entertainment|https://collider.com/feed/
vulture|entertainment|https://www.vulture.com/rss/index.xml
avclub|entertainment|https://www.avclub.com/rss
digitalspy|entertainment|https://www.digitalspy.com/feed/rss/
empire|entertainment|https://www.empireonline.com/feed/rss/
tvline|entertainment|https://tvline.com/feed/
decider|entertainment|https://decider.com/feed/
slashfilm|entertainment|https://www.slashfilm.com/feed/
artnews|culture|https://www.artnews.com/feed/
artnet|culture|https://news.artnet.com/feed
theartnewspaper|culture|https://www.theartnewspaper.com/rss.xml
hyperallergic|culture|https://hyperallergic.com/feed/
lithub|culture|https://lithub.com/feed/
kirkus|culture|https://www.kirkusreviews.com/feeds/reviews/
electricliterature|culture|https://electricliterature.com/feed/
openculture|culture|https://www.openculture.com/feed
marginalian|culture|https://www.themarginalian.org/feed/
eater|food|https://www.eater.com/rss/index.xml
seriouseats|food|https://www.seriouseats.com/rss
bonappetit|food|https://www.bonappetit.com/feed/rss
food52|food|https://food52.com/blog.rss
thekitchn|food|https://www.thekitchn.com/main.rss
delish|food|https://www.delish.com/rss/
saveur|food|https://www.saveur.com/feed/
epicurious|food|https://www.epicurious.com/feed/rss
cntraveler|travel|https://www.cntraveler.com/feed/rss
travelandleisure|travel|https://www.travelandleisure.com/rss
lonelyplanet|travel|https://www.lonelyplanet.com/news/feed
skift|travel|https://skift.com/feed/
roadsandkingdoms|travel|https://roadsandkingdoms.com/feed/
carbonbrief|climate|https://www.carbonbrief.org/feed
grist|climate|https://grist.org/feed/
insideclimate|climate|https://insideclimatenews.org/feed/
yaleclimate|climate|https://yaleclimateconnections.org/feed/
climatehome|climate|https://www.climatechangenews.com/feed/
pew|politics|https://www.pewresearch.org/feed/
brookings|politics|https://www.brookings.edu/feed/
cfr|world|https://www.cfr.org/rss-feeds
foreignpolicy|world|https://foreignpolicy.com/feed/
foreignaffairs|world|https://www.foreignaffairs.com/rss.xml
cjr|education|https://www.cjr.org/feed
niemanlab|education|https://www.niemanlab.org/feed/
globalvoices|world|https://globalvoices.org/feed/
theconversation|science|https://theconversation.com/us/articles.atom
theconversation|science|https://theconversation.com/uk/articles.atom
theconversation|science|https://theconversation.com/au/articles.atom
theconversation|science|https://theconversation.com/africa/articles.atom
dazed|culture|https://www.dazeddigital.com/rss
them|culture|https://www.them.us/feed/rss
refinery29|culture|https://www.refinery29.com/en-us/rss.xml
mashable|tech|https://mashable.com/feeds/rss/all
buzzfeed|culture|https://www.buzzfeed.com/feed.xml
studyinternational|education|https://www.studyinternational.com/feed/
universityworldnews|education|https://www.universityworldnews.com/backend/rss.php
timeshighereducation|education|https://www.timeshighereducation.com/rss
"""


@dataclass(frozen=True)
class FeedSpec:
    id: str
    source_id: str
    topic: str
    url: str
    label: str

    @property
    def kind(self) -> str:
        return "espn" if self.url.startswith("espn-json:") else "rss"


def _feed_id(source_id: str, url: str) -> str:
    import hashlib

    return hashlib.sha1(f"{source_id}|{url}".encode()).hexdigest()[:16]


def _build_catalog() -> tuple[dict[str, Source], list[FeedSpec]]:
    raw_sources: dict[str, dict] = {}
    order: list[str] = []
    problems: list[str] = []

    for line_no, line in enumerate(SOURCES_RAW.splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) != len(_SRC_COLUMNS):
            problems.append(f"source line {line_no}: expected {len(_SRC_COLUMNS)} fields, got {len(parts)}")
            continue
        row = dict(zip(_SRC_COLUMNS, parts))
        sid = row["id"]
        if sid in raw_sources:
            problems.append(f"duplicate source id {sid!r}")
            continue
        topics = [t.strip() for t in row["topics"].split(",") if t.strip()]
        unknown = [t for t in topics if t not in TOPIC_SLUGS]
        if unknown:
            problems.append(f"source {sid}: unknown topics {unknown}")
            topics = [t for t in topics if t in TOPIC_SLUGS]
        if not topics:
            problems.append(f"source {sid}: no valid topics, defaulting to world")
            topics = ["world"]
        lean = row["lean"] if row["lean"] in LEANS else "center"
        audience = row["audience"] if row["audience"] in AUDIENCES else "general"
        raw_sources[sid] = {
            "id": sid,
            "name": row["name"],
            "domain": row["domain"],
            "country": row["country"],
            "region": row["region"] if row["region"] in REGIONS else "Global",
            "lean": lean,
            "paywall": row["paywall"] in ("1", "true", "yes"),
            "audience": audience,
            "topics": tuple(dict.fromkeys(topics)),
            "about": row["about"],
        }
        order.append(sid)

    feeds: list[FeedSpec] = []
    seen_urls: set[str] = set()
    for line_no, line in enumerate(FEEDS_RAW.splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) != 3:
            problems.append(f"feed line {line_no}: expected 3 fields, got {len(parts)}")
            continue
        sid, topic, url = parts
        if sid not in raw_sources:
            problems.append(f"feed line {line_no}: unknown source id {sid!r}")
            continue
        if topic not in TOPIC_SLUGS:
            problems.append(f"feed line {line_no}: unknown topic {topic!r}")
            topic = raw_sources[sid]["topics"][0]
        if url in seen_urls:
            continue
        seen_urls.add(url)
        feeds.append(FeedSpec(id=_feed_id(sid, url), source_id=sid, topic=topic, url=url, label=topic))

    sources: dict[str, Source] = {}
    feeds_by_source: dict[str, list[tuple[str, str, str]]] = {}
    for feed in feeds:
        feeds_by_source.setdefault(feed.source_id, []).append((feed.topic, feed.url, feed.label))
    for sid in order:
        data = raw_sources[sid]
        sources[sid] = Source(feeds=tuple(feeds_by_source.get(sid, ())), **data)

    if problems:
        import logging

        logging.getLogger("pulse.sources").warning(
            "catalog problems (%d): %s", len(problems), "; ".join(problems[:8])
        )
    return sources, feeds


SOURCES, FEEDS = _build_catalog()
SOURCE_BY_ID = SOURCES
FEEDS_BY_SOURCE: dict[str, list[FeedSpec]] = {}
for _feed in FEEDS:
    FEEDS_BY_SOURCE.setdefault(_feed.source_id, []).append(_feed)


def get_source(source_id: str) -> Source | None:
    return SOURCES.get(source_id)


def source_names() -> dict[str, str]:
    return {sid: src.name for sid, src in SOURCES.items()}


def sources_for_topic(topic: str) -> list[Source]:
    return [src for src in SOURCES.values() if topic in src.topics]


def feeds_without_source() -> list[Source]:
    return [src for src in SOURCES.values() if not src.feeds]


def catalog_stats() -> dict:
    countries = sorted({src.country for src in SOURCES.values()})
    return {
        "sources": len(SOURCES),
        "feeds": len(FEEDS),
        "countries": len(countries),
        "topics": len(TOPICS),
        "teen_sources": sum(1 for src in SOURCES.values() if src.teen_friendly),
        "free_sources": sum(1 for src in SOURCES.values() if not src.paywall),
        "json_feeds": sum(1 for f in FEEDS if f.kind == "espn"),
    }


if __name__ == "__main__":  # pragma: no cover - quick catalog sanity check
    import json

    print(json.dumps(catalog_stats(), indent=2))
    missing = [src.name for src in SOURCES.values() if not src.feeds]
    print("sources without feeds:", missing)
