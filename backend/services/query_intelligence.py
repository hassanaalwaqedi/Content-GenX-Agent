"""
Query Intelligence Engine for the Content Intelligence Platform.

Transforms raw user keywords into platform-optimized search variants,
synonym expansions, and relevance matching term sets.  Entirely local —
no external AI or network calls required.

Usage:
    engine = QueryIntelligenceEngine()
    ctx = engine.expand("cutekid")
    # ctx.normalized_terms  → ["cute kid", "cute kids"]
    # ctx.tiktok_variants   → ["cutekid", "#cutekid", "cute kid", ...]
    # ctx.instagram_variants→ ["#cutekid", "#cutekids", "#kidsoftiktok", ...]
    # ctx.synonyms          → ["baby", "toddler", "children", ...]
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Set

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Query Context — the expanded representation of a user keyword
# ---------------------------------------------------------------------------
@dataclass
class QueryContext:
    """
    Full expansion of a single user keyword into platform-aware
    search terms and relevance matching metadata.
    """

    # Original input
    original_keyword: str = ""

    # Normalized/split forms of the keyword
    normalized_terms: List[str] = field(default_factory=list)

    # Platform-specific search variants
    youtube_variants: List[str] = field(default_factory=list)
    tiktok_variants: List[str] = field(default_factory=list)
    instagram_variants: List[str] = field(default_factory=list)
    reddit_variants: List[str] = field(default_factory=list)

    # Synonym expansions
    synonyms: List[str] = field(default_factory=list)

    # Relevance scoring term sets
    required_terms: List[str] = field(default_factory=list)
    soft_terms: List[str] = field(default_factory=list)
    negative_terms: List[str] = field(default_factory=list)

    # All searchable terms combined (for quick matching)
    all_positive_terms: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        """Serialize for logging / transport."""
        return {
            "original_keyword": self.original_keyword,
            "normalized_terms": self.normalized_terms,
            "youtube_variants": self.youtube_variants,
            "tiktok_variants": self.tiktok_variants,
            "instagram_variants": self.instagram_variants,
            "reddit_variants": self.reddit_variants,
            "synonyms": self.synonyms,
            "required_terms": self.required_terms,
            "soft_terms": self.soft_terms,
            "negative_terms": self.negative_terms,
        }


# ---------------------------------------------------------------------------
# Synonym Dictionary — lightweight, local, no external dependencies
# ---------------------------------------------------------------------------
# Each key maps to a set of closely related terms.  The engine checks
# if the keyword (or any normalized term) overlaps with a cluster key
# and returns the rest of the cluster as synonyms.

_SYNONYM_CLUSTERS: Dict[str, List[str]] = {
    # ── Kids / Family ──
    "kid": ["kids", "children", "child", "toddler", "baby", "infant"],
    "cute": ["adorable", "sweet", "lovely", "precious", "charming"],
    "baby": ["infant", "newborn", "toddler", "little one", "babies"],
    "parenting": ["parent", "mom", "dad", "family", "motherhood", "fatherhood"],
    "family": ["parents", "kids", "home", "household", "siblings"],

    # ── Fashion / Style ──
    "fashion": ["style", "outfit", "ootd", "clothing", "apparel", "wardrobe"],
    "style": ["fashion", "outfit", "look", "aesthetic", "trend"],
    "beauty": ["makeup", "skincare", "cosmetics", "glow up", "beauty tips"],

    # ── Marketing / Business ──
    "marketing": ["growth hacking", "social media marketing", "digital marketing",
                   "content strategy", "ugc marketing", "branding"],
    "business": ["entrepreneurship", "startup", "founder", "hustle", "enterprise"],
    "entrepreneur": ["founder", "startup", "business owner", "ceo", "hustle"],
    "brand": ["branding", "identity", "logo", "marketing", "brand strategy"],

    # ── Tech / AI ──
    "tech": ["technology", "coding", "programming", "developer", "software", "gadget"],
    "ai": ["artificial intelligence", "machine learning", "deep learning",
            "chatgpt", "gpt", "automation"],
    "coding": ["programming", "developer", "software", "code", "engineering"],
    "startup": ["tech startup", "saas", "founder", "venture", "innovation"],

    # ── Fitness / Health ──
    "fitness": ["workout", "gym", "exercise", "health", "wellness", "training"],
    "workout": ["exercise", "gym", "fitness", "training", "hiit", "cardio"],
    "health": ["wellness", "nutrition", "diet", "mental health", "self care"],
    "yoga": ["meditation", "mindfulness", "stretching", "wellness", "flexibility"],

    # ── Food / Cooking ──
    "food": ["cooking", "recipe", "foodie", "chef", "meal", "cuisine"],
    "cooking": ["recipe", "kitchen", "chef", "meal prep", "food hack"],
    "recipe": ["cooking", "meal", "dish", "ingredients", "food"],
    "vegan": ["plant based", "vegetarian", "healthy eating", "green", "organic"],

    # ── Entertainment / Content ──
    "comedy": ["funny", "humor", "meme", "joke", "skit", "laugh"],
    "funny": ["comedy", "humor", "hilarious", "meme", "lol"],
    "music": ["song", "artist", "beat", "melody", "concert", "singer"],
    "dance": ["dancing", "choreography", "moves", "dancer", "routine"],
    "gaming": ["gamer", "game", "esports", "gameplay", "streamer", "twitch"],

    # ── Travel / Lifestyle ──
    "travel": ["trip", "vacation", "adventure", "explore", "destination", "wanderlust"],
    "lifestyle": ["daily routine", "vlog", "day in my life", "aesthetic", "minimalist"],
    "motivation": ["inspiration", "grind", "hustle", "mindset", "success", "goals"],

    # ── Education ──
    "education": ["learning", "study", "tutorial", "how to", "tips", "guide"],
    "tutorial": ["how to", "guide", "learn", "step by step", "diy"],

    # ── Finance ──
    "finance": ["money", "investing", "savings", "wealth", "budget", "crypto"],
    "crypto": ["bitcoin", "blockchain", "web3", "nft", "defi", "ethereum"],
    "investing": ["stocks", "portfolio", "trading", "dividends", "wealth"],

    # ── Pets / Animals ──
    "pet": ["pets", "dog", "cat", "puppy", "kitten", "animal"],
    "dog": ["puppy", "doggo", "pup", "canine", "golden retriever"],
    "cat": ["kitten", "kitty", "feline", "cats", "meow"],

    # ── Sports ──
    "sports": ["athlete", "game", "match", "championship", "team", "training"],
    "football": ["soccer", "goal", "match", "premier league", "champions league"],
    "basketball": ["nba", "hoops", "dunk", "court", "bball"],
}

# Pre-build reverse lookup: term → cluster keys
_TERM_TO_CLUSTERS: Dict[str, Set[str]] = {}
for _cluster_key, _terms in _SYNONYM_CLUSTERS.items():
    _TERM_TO_CLUSTERS.setdefault(_cluster_key, set()).add(_cluster_key)
    for _t in _terms:
        _TERM_TO_CLUSTERS.setdefault(_t.lower(), set()).add(_cluster_key)

# Common English words to split compound keywords (word boundary dictionary)
_COMMON_WORDS: FrozenSet[str] = frozenset({
    "cute", "kid", "kids", "baby", "love", "fun", "cool", "best", "top",
    "new", "hot", "big", "my", "the", "how", "why", "what", "day",
    "life", "time", "good", "bad", "real", "home", "food", "tech",
    "fit", "gym", "art", "dog", "cat", "car", "man", "boy", "girl",
    "mom", "dad", "son", "tip", "hack", "try", "get", "use", "make",
    "work", "play", "run", "talk", "show", "look", "feel", "take",
    "give", "go", "see", "come", "say", "know", "think", "want",
    "need", "like", "find", "tell", "ask", "put", "call", "keep",
    "let", "set", "turn", "move", "live", "lose", "pay", "meet",
    "sport", "game", "team", "star", "music", "song", "dance",
    "style", "fashion", "outfit", "beauty", "health", "care", "skin",
    "hair", "nail", "body", "mind", "soul", "heart", "brain",
    "money", "rich", "cash", "gold", "coin", "earn", "save",
    "cook", "chef", "meal", "diet", "vegan", "plant", "organic",
    "travel", "trip", "tour", "city", "beach", "wild", "nature",
    "photo", "video", "reel", "clip", "post", "story", "content",
    "brand", "viral", "trend", "growth", "market", "digital",
    "code", "data", "web", "app", "cloud", "smart", "robot",
    "dark", "light", "fast", "slow", "free", "easy", "hard",
    "little", "small", "tiny", "mini", "super", "mega", "ultra",
    "family", "house", "room", "garden", "pet", "animal",
    "morning", "night", "summer", "winter", "spring", "fall",
    "school", "class", "learn", "study", "book", "read", "write",
    "magic", "secret", "hidden", "simple", "quick", "daily",
    "challenge", "review", "react", "unbox", "haul", "grwm",
})

# Negative/spam terms — content containing these disproportionately is likely irrelevant
_NEGATIVE_INDICATORS: FrozenSet[str] = frozenset({
    "follow for follow", "f4f", "l4l", "like for like",
    "dm for collab", "shoutout", "giveaway", "free followers",
    "link in bio", "cashapp", "onlyfans", "18+", "nsfw",
    "telegram", "whatsapp group", "click link",
})


# ---------------------------------------------------------------------------
# Query Intelligence Engine
# ---------------------------------------------------------------------------
class QueryIntelligenceEngine:
    """
    Expands raw user keywords into platform-optimized search variants
    and relevance matching terms.  Pure local computation — no network
    calls, no LLM, no external dependencies.

    Thread-safe and cacheable.
    """

    def __init__(
        self,
        max_synonyms: int = 5,
        max_hashtag_variants: int = 8,
    ) -> None:
        self._max_synonyms = max_synonyms
        self._max_hashtag_variants = max_hashtag_variants

    # ── Public API ──────────────────────────────────────────────────────────

    def expand(self, keyword: str) -> QueryContext:
        """
        Expand a single keyword into a full QueryContext.

        This is the main entry point.  Results are deterministic
        for the same input.
        """
        if not keyword or not keyword.strip():
            return QueryContext(original_keyword=keyword)

        keyword = keyword.strip()
        kw_lower = keyword.lower()

        logger.info("[QUERY] Expanding keyword: %r", keyword)

        # Step 1: Normalize / split compound keywords
        normalized = self._normalize_keyword(kw_lower)

        # Step 2: Generate synonyms
        synonyms = self._generate_synonyms(kw_lower, normalized)

        # Step 3: Build platform-specific variants
        youtube_variants = self._build_youtube_variants(kw_lower, normalized, synonyms)
        tiktok_variants = self._build_tiktok_variants(kw_lower, normalized, synonyms)
        instagram_variants = self._build_instagram_variants(kw_lower, normalized, synonyms)
        reddit_variants = self._build_reddit_variants(kw_lower, normalized, synonyms)

        # Step 4: Build relevance term sets
        required_terms = [kw_lower] + normalized[:2]
        soft_terms = normalized[2:] + synonyms[: self._max_synonyms]
        negative_terms = list(_NEGATIVE_INDICATORS)

        # Build combined positive terms for matching
        all_positive = list(dict.fromkeys(
            [kw_lower] + normalized + synonyms
        ))

        ctx = QueryContext(
            original_keyword=keyword,
            normalized_terms=normalized,
            youtube_variants=youtube_variants,
            tiktok_variants=tiktok_variants,
            instagram_variants=instagram_variants,
            reddit_variants=reddit_variants,
            synonyms=synonyms,
            required_terms=list(dict.fromkeys(required_terms)),
            soft_terms=list(dict.fromkeys(soft_terms)),
            negative_terms=negative_terms,
            all_positive_terms=all_positive,
        )

        logger.info(
            "[QUERY] expanded_terms=%s synonyms=%s youtube_variants=%d tiktok_variants=%d ig_variants=%d reddit_variants=%d",
            normalized,
            synonyms[:5],
            len(youtube_variants),
            len(tiktok_variants),
            len(instagram_variants),
            len(reddit_variants),
        )

        return ctx

    def expand_multi(self, keywords: List[str]) -> List[QueryContext]:
        """Expand multiple keywords and return a list of QueryContexts."""
        return [self.expand(kw) for kw in keywords if kw and kw.strip()]

    def merge_contexts(self, contexts: List[QueryContext]) -> QueryContext:
        """Merge multiple QueryContexts into a single combined context."""
        if not contexts:
            return QueryContext()
        if len(contexts) == 1:
            return contexts[0]

        merged = QueryContext(
            original_keyword=" + ".join(c.original_keyword for c in contexts),
        )

        def merge_field(name: str) -> None:
            values: List[str] = []
            for context in contexts:
                values.extend(getattr(context, name))
            setattr(merged, name, list(dict.fromkeys(values)))

        for field_name in (
            "normalized_terms",
            "youtube_variants",
            "tiktok_variants",
            "instagram_variants",
            "reddit_variants",
            "synonyms",
            "required_terms",
            "soft_terms",
        ):
            merge_field(field_name)

        merged.negative_terms = list(_NEGATIVE_INDICATORS)
        merged.all_positive_terms = list(dict.fromkeys(
            merged.required_terms + merged.normalized_terms + merged.synonyms
        ))

        return merged

    # ── Keyword Normalization ───────────────────────────────────────────────

    def _normalize_keyword(self, keyword: str) -> List[str]:
        """
        Split compound/concatenated keywords into spaced variants.

        Examples:
            "cutekid"     → ["cute kid", "cute kids"]
            "kidsfashion" → ["kids fashion"]
            "babystyle"   → ["baby style"]
            "cute kid"    → ["cute kid"]  (already spaced)
        """
        results: List[str] = []

        # If already contains spaces, it's already normalized
        if " " in keyword:
            results.append(keyword)
            # Also try without spaces as a hashtag form
            no_spaces = keyword.replace(" ", "")
            if no_spaces != keyword:
                results.append(no_spaces)
            # Try plural/singular variants
            results.extend(self._generate_plural_variants(keyword))
            return list(dict.fromkeys(results))[:6]

        # Try to split the compound keyword using known word boundaries
        splits = self._split_compound_keyword(keyword)
        if splits:
            results.extend(splits)

        # Always include the original
        if keyword not in results:
            results.insert(0, keyword)

        # Add plural/singular variants
        for split in list(results):
            results.extend(self._generate_plural_variants(split))

        return list(dict.fromkeys(results))[:8]

    def _split_compound_keyword(self, word: str) -> List[str]:
        """
        Attempt to split a concatenated word into constituent words.

        Uses a greedy approach matching against the common words dictionary.
        E.g.: "cutekid" → "cute kid", "kidsfashion" → "kids fashion"
        """
        word = word.lower()
        if len(word) < 4:
            return []

        results: List[str] = []

        # Try all possible split points
        for i in range(2, len(word) - 1):
            left = word[:i]
            right = word[i:]

            if left in _COMMON_WORDS and right in _COMMON_WORDS:
                results.append(f"{left} {right}")
            elif left in _COMMON_WORDS and len(right) >= 3:
                # Try splitting the right part further
                for j in range(2, len(right)):
                    rl = right[:j]
                    rr = right[j:]
                    if rl in _COMMON_WORDS and rr in _COMMON_WORDS:
                        results.append(f"{left} {rl} {rr}")

        # Also try camelCase / internal uppercase splits
        camel_split = re.sub(r"([a-z])([A-Z])", r"\1 \2", word).lower()
        if camel_split != word:
            results.append(camel_split)

        return list(dict.fromkeys(results))[:4]

    @staticmethod
    def _generate_plural_variants(phrase: str) -> List[str]:
        """Generate simple plural/singular variants of a phrase."""
        variants: List[str] = []
        words = phrase.split()
        if not words:
            return variants

        last = words[-1]

        # Singular → plural
        if not last.endswith("s"):
            variants.append(" ".join(words[:-1] + [last + "s"]))
        # Plural → singular
        elif last.endswith("s") and len(last) > 3:
            variants.append(" ".join(words[:-1] + [last[:-1]]))

        return variants

    # ── Synonym Expansion ───────────────────────────────────────────────────

    def _generate_synonyms(
        self,
        keyword: str,
        normalized_terms: List[str],
    ) -> List[str]:
        """
        Generate synonym expansions using the local dictionary.

        Checks the keyword and all normalized terms against synonym clusters.
        """
        synonyms: List[str] = []
        seen: Set[str] = {keyword}
        for term in normalized_terms:
            seen.add(term)

        # Check each word against synonym clusters
        check_terms = {keyword}
        for term in normalized_terms:
            check_terms.add(term)
            for word in term.split():
                check_terms.add(word)

        for term in check_terms:
            cluster_keys = _TERM_TO_CLUSTERS.get(term.lower(), set())
            for cluster_key in cluster_keys:
                cluster_terms = _SYNONYM_CLUSTERS.get(cluster_key, [])
                for syn in cluster_terms:
                    if syn.lower() not in seen:
                        seen.add(syn.lower())
                        synonyms.append(syn)

        return synonyms[: self._max_synonyms * 2]

    # ── Platform-Specific Variants ──────────────────────────────────────────

    def _build_youtube_variants(
        self,
        keyword: str,
        normalized: List[str],
        synonyms: List[str],
    ) -> List[str]:
        """Generate concise search phrases for YouTube's keyword search API."""
        variants = [keyword, *normalized[:3], *synonyms[:3]]
        # YouTube search terms are phrases, not hashtags. Preserve order so
        # the operator's original keyword is always searched first.
        return list(dict.fromkeys(term.strip() for term in variants if term.strip()))[:8]

    def _build_reddit_variants(
        self,
        keyword: str,
        normalized: List[str],
        synonyms: List[str],
    ) -> List[str]:
        """Generate plain-language Reddit search terms and community phrases."""
        base = normalized[0] if normalized else keyword
        variants = [keyword, base, *normalized[1:3], *synonyms[:4]]
        return list(dict.fromkeys(term.strip() for term in variants if term.strip()))[:8]

    def _build_tiktok_variants(
        self,
        keyword: str,
        normalized: List[str],
        synonyms: List[str],
    ) -> List[str]:
        """
        Generate TikTok-optimized search terms.

        TikTok search works well with:
        - Direct keywords
        - Hashtag names (without #)
        - Spaced phrases
        - Viral phrase forms ("X be like", "POV: X")
        """
        variants: List[str] = []

        # 1. Original keyword as search term
        variants.append(keyword)

        # 2. Normalized (spaced) forms
        for term in normalized:
            if term != keyword:
                variants.append(term)

        # 3. Hashtag forms (without #, for the hashtag API)
        variants.append(keyword.replace(" ", ""))
        for term in normalized[:3]:
            hashtag = term.replace(" ", "")
            if hashtag not in variants:
                variants.append(hashtag)

        # 4. Viral phrase forms
        viral_templates = [
            "{kw} be like",
            "POV {kw}",
            "{kw} check",
            "{kw} trend",
            "{kw} fyp",
        ]
        base = normalized[0] if normalized else keyword
        for tmpl in viral_templates[:2]:
            viral = tmpl.format(kw=base)
            if viral not in variants:
                variants.append(viral)

        # 5. Top synonyms as search terms
        for syn in synonyms[:3]:
            if syn not in variants:
                variants.append(syn)

        return list(dict.fromkeys(variants))[: self._max_hashtag_variants * 2]

    def _build_instagram_variants(
        self,
        keyword: str,
        normalized: List[str],
        synonyms: List[str],
    ) -> List[str]:
        """
        Generate Instagram-optimized hashtag search terms.

        Instagram discovery works via:
        - Hashtag search (#keyword)
        - Caption keyword matching
        - Niche/creator mapping
        """
        variants: List[str] = []

        # 1. Primary hashtag (no spaces)
        primary_hashtag = keyword.replace(" ", "")
        variants.append(f"#{primary_hashtag}")

        # 2. Normalized hashtag forms
        for term in normalized[:4]:
            tag = f"#{term.replace(' ', '')}"
            if tag not in variants:
                variants.append(tag)

        # 3. Common Instagram suffix hashtags
        ig_suffixes = [
            "sof", "sofinstagram", "sofinsta",
            "life", "love", "vibes", "aesthetic",
            "reels", "viral", "explore",
        ]
        for suffix in ig_suffixes[:4]:
            tag = f"#{primary_hashtag}{suffix}"
            if tag not in variants and len(tag) < 32:
                variants.append(tag)

        # 4. Platform-specific community hashtags
        community_tags = self._get_community_hashtags(keyword, normalized)
        for tag in community_tags:
            if tag not in variants:
                variants.append(tag)

        # 5. Synonym-based hashtags
        for syn in synonyms[:3]:
            tag = f"#{syn.replace(' ', '')}"
            if tag not in variants:
                variants.append(tag)

        return list(dict.fromkeys(variants))[: self._max_hashtag_variants * 2]

    @staticmethod
    def _get_community_hashtags(keyword: str, normalized: List[str]) -> List[str]:
        """
        Return well-known community hashtags related to the keyword.

        These are hand-curated, high-quality Instagram/TikTok community tags
        that have high engagement and strong niche signals.
        """
        all_terms = {keyword} | set(normalized)
        all_words: Set[str] = set()
        for t in all_terms:
            for w in t.split():
                all_words.add(w.lower())

        tags: List[str] = []

        # Map common keywords to known community hashtags
        community_map: Dict[str, List[str]] = {
            "kid": ["#kidsoftiktok", "#kidsfashion", "#momlife", "#parentingtips"],
            "kids": ["#kidsoftiktok", "#kidsfashion", "#kidsofinstagram"],
            "cute": ["#cutevibes", "#cuteness", "#aww"],
            "baby": ["#babystyle", "#babyreels", "#newmom", "#babiesofinstagram"],
            "fashion": ["#fashiontiktok", "#ootd", "#fashionreels", "#styleinspo"],
            "style": ["#styleinspo", "#fashiondiaries", "#lookoftheday"],
            "food": ["#foodtiktok", "#foodreels", "#foodie", "#yummy"],
            "cooking": ["#cookingtiktok", "#recipeshare", "#homecook"],
            "fitness": ["#fitnesstiktok", "#gymtok", "#workoutmotivation"],
            "workout": ["#workoutroutine", "#fitfam", "#gymlife"],
            "tech": ["#techtok", "#techreview", "#gadgets"],
            "marketing": ["#marketingtips", "#socialmediatips", "#digitalmarketing"],
            "beauty": ["#beautytok", "#makeuptutorial", "#skincareroutine"],
            "travel": ["#traveltok", "#travelreels", "#wanderlust"],
            "music": ["#musictok", "#newmusic", "#musician"],
            "dance": ["#dancetok", "#dancechallenge", "#choreography"],
            "comedy": ["#comedytiktok", "#funnyvideos", "#humor"],
            "gaming": ["#gamingtiktok", "#gamingclips", "#gamer"],
            "dog": ["#dogsoftiktok", "#doglovers", "#puppylove"],
            "cat": ["#catsoftiktok", "#catlovers", "#kitten"],
            "pet": ["#petsoftiktok", "#petlover", "#furbaby"],
        }

        for word in all_words:
            if word in community_map:
                tags.extend(community_map[word])

        return list(dict.fromkeys(tags))[:6]
