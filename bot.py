# ---------- Prayer times ----------
def format_12h(t24):
    clean = t24.split(" ")[0].strip()
    return datetime.strptime(clean, "%H:%M").strftime("%I:%M %p").replace("AM", "ص").replace("PM", "م")

def fetch_prayer_times(gov_key):
    gov_ar, lat, lon = SYRIA_GOVERNORATES[gov_key]
    greg_date, hijri_date = "تاريخ غير متاح", ""
    keys = ["Fajr", "Sunrise", "Dhuhr", "Asr", "Maghrib", "Isha"]
    times = {k: "--:--" for k in keys}
    try:
        resp = requests.get("https://api.aladhan.com/v1/timings", params={
            "latitude": lat, "longitude": lon,
            "method": PRAYER_METHOD,
            "timezonestring": "Asia/Damascus",
            "tune": PRAYER_TUNE,
        }, timeout=10)
        data = resp.json()["data"]
        en_day = data["date"]["gregorian"]["weekday"]["en"]
        greg_date = f"{ARABIC_DAYS.get(en_day, '')} {data['date']['gregorian']['date']} م"
        h = data["date"]["hijri"]
        hijri_date = f"{h['day']} {h['month']['ar']} {h['year']} هـ"
        for k in keys:
            times[k] = format_12h(data["timings"][k])
    except Exception as e:
        print(f"Error fetching times: {e}")
    return gov_ar, greg_date, hijri_date, times
