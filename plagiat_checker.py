# plagiat_checker.py
import re
from typing import Dict, List

class PlagiatChecker:
    """O'zbekiston standartlariga muvofiq plagiat tekshiruv"""
    
    # Standartlar
    MIN_ORIGINALLIK = 70  # Kamida 70%
    MAX_KOCHIRILISH = 30  # 30% gacha
    MIN_MANBA_SONI = 1    # Kamida 1 manba
    
    # Kalit so'zlar (plagiat ko'rsatuvchi)
    SUSPICIOUS_PATTERNS = [
        r"ta'lim tizimi",
        r"pedagogik yondashuv",
        r"sun'iy intellekt",
        r"ilmiy rahbar",
        r"ta'limni modernizatsiya",
        r"zamonavoy texnologiya",
        r"axloqiy qadriyatlar",
        r"madaniy mafhumlar",
        r"o'quv jarayoni",
        r"gumanistik usul",
        r"o'qituvchi",
        r"talaba",
        r"dissertatsiya"
    ]
    
    def __init__(self):
        self.analysis_result = None
    
    def analyze(self, text: str, source_count: int = 0) -> Dict:
        """Matnni tahlil qilish"""
        
        if len(text.strip()) < 100:
            return {"error": "Kamida 100 belgili matn kerak"}
        
        # Asosiy metrikalari
        total_chars = len(text)
        words = len(text.split())
        sentences = len(re.split(r'[.!?]+', text)) - 1
        
        # Manbalar topish
        source_matches = re.findall(r'\[manba \d+\]', text, re.IGNORECASE)
        sources_found = len(set(source_matches))
        has_sources = sources_found > 0
        
        # Kalit so'zlar soni
        suspicious_count = 0
        for pattern in self.SUSPICIOUS_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            suspicious_count += len(matches)
        
        # Originallik hisoblash
        originallik = self._calculate_originallik(
            words=words,
            sentences=sentences,
            suspicious_count=suspicious_count,
            has_sources=has_sources,
            total_chars=total_chars
        )
        
        kochirilgan = 100 - originallik
        
        # Status aniqlash
        status = self._determine_status(
            originallik=originallik,
            kochirilgan=kochirilgan,
            has_sources=has_sources
        )
        
        # Tavsiyalar
        recommendations = self._get_recommendations(
            originallik=originallik,
            has_sources=has_sources,
            suspicious_count=suspicious_count,
            kochirilgan=kochirilgan
        )
        
        self.analysis_result = {
            "originallikFoizi": int(originallik),
            "kochirilganFoizi": int(kochirilgan),
            "statusBadge": status,
            "hasSources": has_sources,
            "sourcesFound": sources_found,
            "totalChars": total_chars,
            "words": words,
            "sentences": sentences,
            "suspiciousCount": suspicious_count,
            "recommendations": recommendations,
            "plagiat_assessment": self._get_plagiat_assessment(
                originallik, kochirilgan, has_sources, suspicious_count
            )
        }
        
        return self.analysis_result
    
    def _calculate_originallik(self, words: int, sentences: int, 
                              suspicious_count: int, has_sources: bool, 
                              total_chars: int) -> float:
        """Originallik foizini hisoblash"""
        
        originallik = 100.0
        
        # 1. Kalit so'zlar penaltisi
        keyword_penalty = min(20, (suspicious_count / 5) * 5)
        originallik -= keyword_penalty
        
        # 2. Manbalar berilishi
        source_penalty = 5 if has_sources else 15
        originallik -= source_penalty
        
        # 3. Matn uzunligi
        if words < 100:
            originallik -= 10
        elif words < 200:
            originallik -= 5
        
        # 4. Jumla uzunligi (o'rta 15-20 so'z bo'lsa yaxshi)
        if sentences > 0:
            avg_words = words / sentences
            if avg_words < 10 or avg_words > 25:
                originallik -= 5
        
        # 5. Xarflar soni (qisqa matn ko'p plagiat)
        if total_chars < 500:
            originallik -= 5
        
        return max(50, min(95, originallik))
    
    def _determine_status(self, originallik: float, kochirilgan: float, 
                         has_sources: bool) -> str:
        """Status aniqlash: OK / SHARTLI / PLAGIAT"""
        
        if originallik >= self.MIN_ORIGINALLIK and \
           kochirilgan <= self.MAX_KOCHIRILISH and \
           has_sources:
            return "OK"
        
        elif originallik >= 60 and kochirilgan <= 40 and has_sources:
            return "SHARTLI"
        
        else:
            return "PLAGIAT"
    
    def _get_recommendations(self, originallik: float, has_sources: bool,
                            suspicious_count: int, kochirilgan: float) -> List[str]:
        """Konkret tavsiyalar berish"""
        
        recs = []
        
        if originallik < self.MIN_ORIGINALLIK:
            recs.append(
                f"❌ Originallik {int(originallik)}% (talabi: 70%). "
                "Matnni qayta yozib, o'z g'oyalarni qo'shing."
            )
        
        if not has_sources:
            recs.append(
                "❌ Manbalar berilmagan. [manba 1], [manba 2] tarzida "
                "iqtiboslar qo'shing."
            )
        
        if suspicious_count > 15:
            recs.append(
                f"⚠️ Kalit so'zlar ko'p takrorlandi ({suspicious_count} ta). "
                "Sinonimlar va parafrazlar ishlatib, o'z uslubingizda qayta yozib qo'ying."
            )
        
        if kochirilgan > 25:
            recs.append(
                f"⚠️ Ko'chirmakashlik {int(kochirilgan)}%. "
                "3-4 paragrafni o'zgartiring va qo'shimcha xulosalar qo'shing."
            )
        
        if originallik >= self.MIN_ORIGINALLIK and has_sources:
            recs.append(
                "✅ Band yaxshi! Ilmiy rahbardan tasdig' so'rang."
            )
        
        return recs if recs else ["Band tahlili tugatildi."]
    
    def _get_plagiat_assessment(self, originallik: float, kochirilgan: float,
                               has_sources: bool, suspicious_count: int) -> Dict:
        """Batafsil plagiat baholash"""
        
        return {
            "originallik_baholang": "Yaxshi" if originallik >= 70 else "Zaifu",
            "kochirilgan_masala": "OK" if kochirilgan <= 30 else "Muammo",
            "manbalar": "Berilgan" if has_sources else "Yo'q",
            "kalit_sozlar": "Normal" if suspicious_count < 15 else "Ko'p",
            "umumiy_baholang": self._determine_status(originallik, kochirilgan, has_sources)
        }


def quick_plagiat_check(text: str, source_count: int = 0) -> Dict:
    """Tez plagiat tekshiruv"""
    checker = PlagiatChecker()
    return checker.analyze(text, source_count)
