# ============================================================
# 推演台 V9.6 - GitHub Actions 自动运行版
# ============================================================

import json
import requests
import subprocess
import sys
import os
import importlib
from datetime import datetime
from math import exp, factorial
import warnings
warnings.filterwarnings('ignore')

# ---------- 自动安装依赖 ----------
deps = ['requests', 'pandas', 'numpy', 'beautifulsoup4']
for pkg in deps:
    try:
        importlib.import_module(pkg)
    except ImportError:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', pkg, '--quiet'])

import pandas as pd
import numpy as np
from bs4 import BeautifulSoup

# ---------- 数据采集 ----------
def collect_data():
    print("📡 数据采集开始...")
    results = {}
    
    # ESPN
    try:
        resp = requests.get("https://site.api.espn.com/apis/site/v2/sports/soccer/eng.1/scoreboard", timeout=10)
        if resp.ok:
            results['espn'] = resp.json()
    except:
        pass
    
    # OpenLigaDB
    try:
        resp = requests.get("https://api.openligadb.de/api/getmatchdata/bl1/2024", timeout=10)
        if resp.ok:
            results['openligadb'] = resp.json()
    except:
        pass
    
    # TheSportsDB
    try:
        resp = requests.get("https://www.thesportsdb.com/api/v1/json/3/lookuptable.php?leagueid=4328", timeout=10)
        if resp.ok:
            results['thesportsdb'] = resp.json()
    except:
        pass
    
    print(f"✅ 数据采集完成，共 {len(results)} 个数据源")
    return results

# ---------- 泊松推演 ----------
def poisson_prob(lam, k):
    return (lam ** k * exp(-lam)) / factorial(k)

def predict_match(home_avg=1.5, away_avg=1.3):
    lam_h, lam_a = home_avg, away_avg
    max_goals = 5
    home_win = draw = away_win = 0
    for hg in range(max_goals+1):
        for ag in range(max_goals+1):
            p = poisson_prob(lam_h, hg) * poisson_prob(lam_a, ag)
            if hg > ag:
                home_win += p
            elif hg < ag:
                away_win += p
            else:
                draw += p
    over_25 = 0
    for total in range(3, 10):
        p = 0
        for hg in range(total+1):
            ag = total - hg
            if ag >= 0:
                p += poisson_prob(lam_h, hg) * poisson_prob(lam_a, ag)
        over_25 += p
    return {
        'home_win': round(home_win, 3),
        'draw': round(draw, 3),
        'away_win': round(away_win, 3),
        'over_25': round(over_25, 3),
        'under_25': round(1 - over_25, 3),
        'expected_goals': round(lam_h + lam_a, 2)
    }

def parse_espn(data):
    events = data.get('events', [])
    matches = []
    for e in events:
        comp = e.get('competitions', [{}])[0]
        comps = comp.get('competitors', [])
        if len(comps) < 2:
            continue
        home, away = comps[0], comps[1]
        matches.append({
            'home': home.get('team', {}).get('displayName', ''),
            'away': away.get('team', {}).get('displayName', ''),
            'status': e.get('status', {}).get('type', {}).get('description', '')
        })
    return matches

def run_pushi(data):
    matches = parse_espn(data.get('espn', {}))
    if not matches:
        return [{'error': '无比赛数据'}]
    results = []
    for m in matches[:10]:
        pred = predict_match(1.5, 1.3)
        results.append({
            'match': f"{m['home']} vs {m['away']}",
            'status': m['status'],
            'probability': pred,
            'expected_goals': pred['expected_goals']
        })
    return results

def generate_report(results):
    lines = []
    lines.append("="*60)
    lines.append(f"🏆 推演报告 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("="*60)
    for r in results:
        if 'error' in r:
            lines.append(f"❌ {r['error']}")
            continue
        p = r['probability']
        lines.append(f"\n🆚 {r['match']}  ({r['status']})")
        lines.append(f"  主胜: {p['home_win']:.1%}  平局: {p['draw']:.1%}  客胜: {p['away_win']:.1%}")
        lines.append(f"  大2.5: {p['over_25']:.1%}  小2.5: {p['under_25']:.1%}  期望进球: {p['expected_goals']}")
    lines.append("\n" + "="*60)
    return "\n".join(lines)

def send_telegram(report):
    token = os.environ.get('TELEGRAM_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    if not token or not chat_id:
        print("⚠️ Telegram配置不完整，跳过发送")
        return
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        if len(report) > 4000:
            report = report[:4000] + "\n... (截断)"
        resp = requests.post(url, data={'chat_id': chat_id, 'text': report})
        if resp.ok:
            print("✅ Telegram发送成功")
        else:
            print(f"❌ Telegram发送失败: {resp.text}")
    except Exception as e:
        print(f"❌ Telegram异常: {e}")

def main():
    print("🚀 推演台自动运行开始...")
    data = collect_data()
    results = run_pushi(data)
    report = generate_report(results)
    print(report)
    
    with open('report.txt', 'w', encoding='utf-8') as f:
        f.write(report)
    with open('report.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    send_telegram(report)
    print("✅ 推演完成！")

if __name__ == "__main__":
    main()
