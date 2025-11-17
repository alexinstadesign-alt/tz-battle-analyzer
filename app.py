import requests
import time
import re
import json
from collections import defaultdict
from datetime import datetime
from flask import Flask, render_template_string
import threading
import os

# ВАЖНО: Flask приложение должно называться 'app'
app = Flask(__name__)

class RenderBattleAnalyzer:
    def __init__(self):
        self.players_resources = defaultdict(lambda: {
            'Metals': 0, 'Precious metals': 0, 'Polymers': 0, 'Organic': 0,
            'Silicon': 0, 'Radioactive': 0, 'Gems': 0, 'Venom': 0,
            'battles_count': 0
        })
        self.processed_battles = set()
        self.last_battle_id = 2785756
        self.is_running = True
        self.last_update = datetime.now()
        self.start_time = datetime.now()
        
        self.resource_icons = {
            'Metals': 'https://iili.io/fJMpEWg.png',
            'Precious metals': 'https://iili.io/fJMpcOP.png', 
            'Polymers': 'https://iili.io/fJMplb1.png',
            'Organic': 'https://iili.io/fJMp1zF.png',
            'Silicon': 'https://iili.io/fJMpXgR.png',
            'Radioactive': 'https://iili.io/fJMpW0v.png',
            'Gems': 'https://iili.io/fJMbqBf.png',
            'Venom': 'https://iili.io/fJMpjJp.png'
        }
        print("🚀 Render Battle Analyzer инициализирован!")

    def download_battle(self, battle_id):
        """Загружает бой по ID"""
        url = f"http://realm-battle.tz-game.com/{battle_id}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': '*/*'
        }
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200 and '<BATTLE' in response.text:
                return response.text, "success"
            return None, "failed"
        except Exception as e:
            return None, f"error: {str(e)}"

    def analyze_battle(self, content, battle_id):
        """Анализирует бой"""
        try:
            # Ищем игроков
            players = re.findall(r'rlogin_utf8="([^"$][^"]*)"', content)
            real_players = [p for p in players if not p.startswith('$')]
            
            if not real_players:
                return False
            
            # Ищем ресурсы
            resources_by_player = {player: defaultdict(int) for player in real_players}
            pickup_events = re.findall(r'<a sf="\d+" t="8" id="\d+" txt="([^"]+)" count="(\d+)"', content)
            
            for item_name, count in pickup_events:
                count = int(count)
                resource_type = None
                item_lower = item_name.lower()
                
                if 'metal' in item_lower: resource_type = 'Metals'
                elif 'gold' in item_lower or 'precious' in item_lower: resource_type = 'Precious metals'
                elif 'polymer' in item_lower: resource_type = 'Polymers'
                elif 'organic' in item_lower: resource_type = 'Organic'
                elif 'silicon' in item_lower: resource_type = 'Silicon'
                elif 'radioactive' in item_lower: resource_type = 'Radioactive'
                elif 'gem' in item_lower: resource_type = 'Gems'
                elif 'venom' in item_lower: resource_type = 'Venom'
                
                if resource_type:
                    for player in real_players:
                        resources_by_player[player][resource_type] += count
            
            # Обновляем данные
            for player in real_players:
                self.players_resources[player]['battles_count'] += 1
                for resource, amount in resources_by_player[player].items():
                    self.players_resources[player][resource] += amount
            
            self.processed_battles.add(battle_id)
            self.last_update = datetime.now()
            return True
            
        except Exception as e:
            print(f"Ошибка анализа: {e}")
            return False

    def calculate_totals(self):
        """Считает общие суммы"""
        for player in self.players_resources:
            resources = self.players_resources[player]
            resources['Total'] = sum(resources[r] for r in [
                'Metals', 'Precious metals', 'Polymers', 'Organic', 
                'Silicon', 'Radioactive', 'Gems', 'Venom'
            ])

    def monitor(self):
        """Основной цикл"""
        current_id = self.last_battle_id
        failures = 0
        
        print("🚀 Запуск автономного мониторинга...")
        
        while self.is_running and failures < 50:
            content, status = self.download_battle(current_id)
            
            if content and status == "success":
                if self.analyze_battle(content, current_id):
                    print(f"✅ Бой {current_id} - УСПЕХ")
                    self.last_battle_id = current_id
                    failures = 0
                else:
                    failures += 1
                    print(f"⚠️ Бой {current_id} - нет данных")
            else:
                failures += 1
                if failures % 10 == 0:
                    print(f"❌ Бой {current_id} - {status}")
            
            current_id += 1
            time.sleep(1)
            
            # Периодический вывод статистики
            if len(self.processed_battles) % 5 == 0 and len(self.processed_battles) > 0:
                print(f"📊 Прогресс: {len(self.processed_battles)} боев, {len(self.players_resources)} игроков")

    def get_stats(self):
        """Статистика для веба"""
        self.calculate_totals()
        uptime = datetime.now() - self.start_time
        
        # Сортируем по общему количеству
        sorted_players = dict(sorted(
            self.players_resources.items(),
            key=lambda x: x[1]['Total'],
            reverse=True
        )[:50])  # Только топ 50
        
        return {
            'processed_battles': len(self.processed_battles),
            'players_count': len(self.players_resources),
            'current_battle_id': self.last_battle_id,
            'last_update': self.last_update,
            'uptime': str(uptime).split('.')[0],
            'players_data': sorted_players,
            'resource_icons': self.resource_icons
        }

# Создаем анализатор
analyzer = RenderBattleAnalyzer()

def start_monitoring():
    """Запуск в фоне"""
    try:
        analyzer.monitor()
    except Exception as e:
        print(f"💥 Ошибка мониторинга: {e}")

# Запускаем мониторинг в фоновом потоке
print("🔄 Запуск фонового мониторинга...")
monitor_thread = threading.Thread(target=start_monitoring, daemon=True)
monitor_thread.start()

# HTML шаблон
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TZ Battle Analyzer</title>
    <style>
        body { 
            font-family: Arial, sans-serif; 
            margin: 0; 
            padding: 20px; 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }
        .container { 
            max-width: 1400px; 
            margin: 0 auto; 
            background: white; 
            padding: 25px; 
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }
        .header { 
            text-align: center; 
            margin-bottom: 30px;
            background: linear-gradient(135deg, #4CAF50, #45a049);
            color: white;
            padding: 20px;
            border-radius: 10px;
        }
        .stats { 
            background: #e3f2fd; 
            padding: 20px; 
            border-radius: 10px; 
            margin-bottom: 25px;
            border-left: 5px solid #2196F3;
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-top: 15px;
        }
        .stat-item {
            background: white;
            padding: 12px;
            border-radius: 8px;
            text-align: center;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        table { 
            width: 100%; 
            border-collapse: collapse; 
            font-size: 13px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        th, td { 
            padding: 10px 8px; 
            border: 1px solid #e0e0e0; 
            text-align: left; 
        }
        th { 
            background: linear-gradient(135deg, #4CAF50, #45a049);
            color: white; 
            position: sticky;
            top: 0;
            font-weight: 600;
        }
        tr:nth-child(even) { background: #f8f9fa; }
        tr:hover { background: #e8f5e8; }
        .resource-cell { 
            display: flex; 
            align-items: center; 
            gap: 6px; 
            font-weight: 500;
        }
        .resource-icon { 
            width: 18px; 
            height: 18px; 
            border-radius: 3px;
        }
        .total-column { 
            background: #e8f5e8; 
            font-weight: bold; 
            font-size: 14px;
        }
        .player-name {
            font-weight: 600;
            color: #2c3e50;
        }
        .controls { 
            text-align: center; 
            margin: 25px 0; 
        }
        .btn {
            padding: 12px 25px;
            background: linear-gradient(135deg, #4CAF50, #45a049);
            color: white;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 600;
            margin: 0 10px;
            transition: transform 0.2s;
        }
        .btn:hover {
            transform: translateY(-2px);
        }
        .footer {
            text-align: center;
            margin-top: 25px;
            color: #666;
            font-size: 12px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎮 TimeZero Battle Analyzer</h1>
            <p>Автономный мониторинг 24/7 • Render.com</p>
        </div>
        
        <div class="stats">
            <h3>📊 Статистика системы</h3>
            <div class="stats-grid">
                <div class="stat-item">
                    <strong>Обработано боев</strong><br>
                    <span style="font-size: 24px; color: #4CAF50;">{{ stats.processed_battles }}</span>
                </div>
                <div class="stat-item">
                    <strong>Найдено игроков</strong><br>
                    <span style="font-size: 24px; color: #2196F3;">{{ stats.players_count }}</span>
                </div>
                <div class="stat-item">
                    <strong>Текущий ID</strong><br>
                    <span style="font-size: 24px; color: #FF9800;">{{ stats.current_battle_id }}</span>
                </div>
                <div class="stat-item">
                    <strong>Время работы</strong><br>
                    <span style="font-size: 18px; color: #9C27B0;">{{ stats.uptime }}</span>
                </div>
            </div>
            <div style="margin-top: 15px; text-align: center;">
                <small>Последнее обновление: {{ stats.last_update.strftime('%Y-%m-%d %H:%M:%S') }}</small>
            </div>
        </div>

        <div class="controls">
            <button class="btn" onclick="location.reload()">🔄 Обновить данные</button>
            <button class="btn" onclick="exportData()">📥 Экспорт JSON</button>
        </div>

        <h2>🎯 Топ игроков по ресурсам</h2>
        <div style="overflow-x: auto; border-radius: 8px; border: 1px solid #e0e0e0;">
            <table>
                <thead>
                    <tr>
                        <th>#</th>
                        <th>Игрок</th>
                        <th>Боев</th>
                        {% for resource in ['Metals', 'Precious metals', 'Polymers', 'Organic', 'Silicon', 'Radioactive', 'Gems', 'Venom'] %}
                        <th>
                            <div class="resource-cell">
                                <img src="{{ stats.resource_icons[resource] }}" class="resource-icon">
                                {{ resource }}
                            </div>
                        </th>
                        {% endfor %}
                        <th class="total-column">Всего</th>
                    </tr>
                </thead>
                <tbody>
                    {% for player, data in stats.players_data.items() %}
                    <tr>
                        <td>{{ loop.index }}</td>
                        <td class="player-name">{{ player }}</td>
                        <td><strong>{{ data.battles_count }}</strong></td>
                        {% for resource in ['Metals', 'Precious metals', 'Polymers', 'Organic', 'Silicon', 'Radioactive', 'Gems', 'Venom'] %}
                        <td>{{ "{:,}".format(data[resource]) }}</td>
                        {% endfor %}
                        <td class="total-column"><strong>{{ "{:,}".format(data.Total) }}</strong></td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        
        <div class="footer">
            <p>🚀 Система работает автономно • Автообновление каждые 30 секунд</p>
        </div>
    </div>
    
    <script>
        function exportData() {
            fetch('/api/stats')
                .then(response => response.json())
                .then(data => {
                    const dataStr = JSON.stringify(data, null, 2);
                    const dataBlob = new Blob([dataStr], {type: 'application/json'});
                    const url = URL.createObjectURL(dataBlob);
                    const link = document.createElement('a');
                    link.href = url;
                    link.download = 'tz_battle_data.json';
                    document.body.appendChild(link);
                    link.click();
                    document.body.removeChild(link);
                    URL.revokeObjectURL(url);
                });
        }
        
        // Автообновление каждые 30 секунд
        setTimeout(() => location.reload(), 30000);
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    stats = analyzer.get_stats()
    return render_template_string(HTML_TEMPLATE, stats=stats)

@app.route('/api/stats')
def api_stats():
    return analyzer.get_stats()

@app.route('/health')
def health():
    return {'status': 'healthy', 'timestamp': datetime.now().isoformat()}

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 10000))
    print(f"🌐 Веб-сервер запущен на порту {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
