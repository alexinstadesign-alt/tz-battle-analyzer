import requests
import os
import time
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from datetime import datetime, timedelta
import json

class RealTimeBattleAnalyzer:
    def __init__(self, start_battle_id=None):
        self.players_resources = defaultdict(lambda: {
            'Metals': 0, 'Precious metals': 0, 'Polymers': 0, 'Organic': 0,
            'Silicon': 0, 'Radioactive': 0, 'Gems': 0, 'Venom': 0,
            'battles_count': 0, 'other_items': [], 'battle_details': []
        })
        self.processed_battles = set()
        self.html_report = "resources_report.html"
        self.last_battle_id = start_battle_id
        self.failed_battles = {}
        self.is_running = True
        
        # URL иконок ресурсов
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

    def find_start_battle_id(self):
        """Находит оптимальную точку старта для последовательных ID"""
        if self.last_battle_id is not None:
            return self.last_battle_id
            
        # Из HTML отчета
        if os.path.exists(self.html_report):
            try:
                with open(self.html_report, 'r', encoding='utf-8') as f:
                    content = f.read()
                    battle_matches = re.findall(r'Бой #(\d+)', content)
                    if battle_matches:
                        return max(map(int, battle_matches)) + 1
            except:
                pass

        # Из лог файла
        if os.path.exists('battle_analyzer.log'):
            try:
                with open('battle_analyzer.log', 'r', encoding='utf-8') as f:
                    lines = f.readlines()[-100:]
                    for line in reversed(lines):
                        if 'Скачан бой' in line or 'Проанализирован бой' in line:
                            battle_id = re.search(r'бой (\d+)', line)
                            if battle_id:
                                return int(battle_id.group(1)) + 1
            except:
                pass

        return 2785756

    def save_last_battle_id(self, battle_id):
        """Сохраняет последний обработанный ID в файл"""
        try:
            with open('last_battle_id.txt', 'w') as f:
                f.write(str(battle_id))
        except:
            pass

    def probe_current_battle_id(self):
        """Ищет актуальный ID боя проверкой последовательных номеров"""
        start_id = self.find_start_battle_id()
        
        # Проверяем небольшой диапазон вперед
        test_range = range(start_id, start_id + 20)
        valid_battles = []
        
        for battle_id in test_range:
            filename, bid, status = self.download_single_battle(battle_id)
            
            if filename and status == "success":
                valid_battles.append(battle_id)
                self.delete_temp_file(filename)
                
                if len(valid_battles) >= 2:
                    return max(valid_battles)
                    
            time.sleep(0.1)
        
        if valid_battles:
            return max(valid_battles)
        else:
            return start_id

    def download_single_battle(self, battle_id):
        """Загружает один бой по ID"""
        url = f"http://realm-battle.tz-game.com/{battle_id}"
        headers = {
            'Accept': 'image/gif, image/x-xbitmap, image/jpeg, image/pjpeg, */*',
            'User-Agent': 'TimeZero Shell (v. 7.1.2.6)',
            'Pragma': 'no-cache'
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=8)
            
            if response.status_code == 200:
                content = response.text
                if '<BATTLE' not in content:
                    return None, battle_id, "invalid_battle"
                    
                filename = f"temp_battle_{battle_id}.dat"
                with open(filename, 'wb') as f:
                    f.write(response.content)
                return filename, battle_id, "success"
                
            elif response.status_code == 404:
                return None, battle_id, "not_found"
            else:
                return None, battle_id, f"http_error_{response.status_code}"
                
        except requests.exceptions.Timeout:
            return None, battle_id, "timeout"
        except requests.exceptions.ConnectionError:
            return None, battle_id, "connection_error"
        except Exception as e:
            return None, battle_id, f"error: {str(e)}"

    def parse_battle_time(self, content):
        """Парсит время боя из лога"""
        time_match = re.search(r'time="(\d+)"', content)
        if time_match:
            timestamp = int(time_match.group(1))
            battle_time = datetime.fromtimestamp(timestamp)
            return battle_time, timestamp
        return None, None

    def parse_battle_location(self, content):
        """Парсит локацию боя"""
        location_match = re.search(r'note="([^"]+)"', content)
        if location_match:
            note_parts = location_match.group(1).split(',')
            if len(note_parts) >= 2:
                return f"Локация {note_parts[0]},{note_parts[1]}"
        return "Неизвестная локация"

    def analyze_single_battle(self, filename, battle_id):
        """Анализирует один файл боя"""
        try:
            with open(filename, 'r', encoding='utf-8', errors='ignore') as file:
                content = file.read()
            
            battle_time, timestamp = self.parse_battle_time(content)
            location = self.parse_battle_location(content)
            
            if not battle_time:
                return False
            
            players = re.findall(r'rlogin_utf8="([^"$][^"]*)"', content)
            real_players = [p for p in players if not p.startswith('$')]
            
            if not real_players:
                return False
            
            battle_resources = self.extract_resources_from_battle(content, real_players)
            
            for player in real_players:
                self.players_resources[player]['battles_count'] += 1
                
                battle_detail = {
                    'battle_id': battle_id,
                    'time': battle_time,
                    'timestamp': timestamp,
                    'location': location,
                    'resources': battle_resources.get(player, {}),
                    'total_resources': sum(battle_resources.get(player, {}).values())
                }
                self.players_resources[player]['battle_details'].append(battle_detail)
                
                for resource_type, amount in battle_resources.get(player, {}).items():
                    if resource_type in self.players_resources[player]:
                        self.players_resources[player][resource_type] += amount
            
            self.processed_battles.add(battle_id)
            return True
                
        except Exception as e:
            print(f"Ошибка при анализе файла {filename}: {e}")
            return False

    def extract_resources_from_battle(self, content, real_players):
        """Извлекает ресурсы из содержимого боя"""
        resources_by_player = {player: defaultdict(int) for player in real_players}
        
        pickup_events = re.findall(r'<a sf="\d+" t="8" id="\d+" txt="([^"]+)" count="(\d+)"', content)
        
        for item_name, count in pickup_events:
            count = int(count)
            
            resource_type = None
            if 'Metals' in item_name:
                resource_type = 'Metals'
            elif 'Gold' in item_name or 'Precious' in item_name:
                resource_type = 'Precious metals'
            elif 'Polymers' in item_name:
                resource_type = 'Polymers'
            elif 'Organic' in item_name:
                resource_type = 'Organic'
            elif 'Silicon' in item_name:
                resource_type = 'Silicon'
            elif 'Radioactive' in item_name:
                resource_type = 'Radioactive'
            elif 'Gems' in item_name:
                resource_type = 'Gems'
            elif 'Venom' in item_name:
                resource_type = 'Venom'
            
            if resource_type:
                for player in real_players:
                    resources_by_player[player][resource_type] += count
            else:
                for player in real_players:
                    if item_name not in self.players_resources[player]['other_items']:
                        self.players_resources[player]['other_items'].append(item_name)
        
        return resources_by_player

    def calculate_totals(self):
        """Рассчитывает общее количество ресурсов"""
        for player, resources in self.players_resources.items():
            resources['Total'] = sum(resources[res] for res in [
                'Metals', 'Precious metals', 'Polymers', 'Organic', 
                'Silicon', 'Radioactive', 'Gems', 'Venom'
            ])

    def cleanup_temp_files(self):
        """Очищает временные файлы"""
        temp_files = list(Path('.').glob('temp_battle_*.*'))
        for temp_file in temp_files:
            try:
                os.remove(temp_file)
            except:
                pass

    def delete_temp_file(self, filename):
        """Удаляет один временный файл"""
        try:
            if filename and os.path.exists(filename):
                os.remove(filename)
                return True
        except:
            pass
        return False

    def generate_html_report(self):
        """Генерирует HTML отчет со всеми функциями"""
        self.calculate_totals()
        
        # Получаем диапазон дат
        all_times = []
        for player_data in self.players_resources.values():
            for battle in player_data['battle_details']:
                all_times.append(battle['time'])
        
        min_date = min(all_times) if all_times else datetime.now() - timedelta(days=30)
        max_date = max(all_times) if all_times else datetime.now()
        
        # Преобразуем данные для JavaScript
        players_data_js = {}
        for player, data in self.players_resources.items():
            players_data_js[player] = {
                'battles_count': data['battles_count'],
                'Metals': data['Metals'],
                'Precious metals': data['Precious metals'],
                'Polymers': data['Polymers'],
                'Organic': data['Organic'],
                'Silicon': data['Silicon'],
                'Radioactive': data['Radioactive'],
                'Gems': data['Gems'],
                'Venom': data['Venom'],
                'Total': data['Total'],
                'battle_details': data['battle_details']
            }
        
        html_content = self.create_html_template(min_date, max_date, players_data_js)
        
        with open(self.html_report, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        return self.html_report

    def create_html_template(self, min_date, max_date, players_data_js):
        """Создает HTML шаблон со всеми функциями"""
        return f"""
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TimeZero Battle Analyzer</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }
        .container {
            max-width: 1800px;
            margin: 0 auto;
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h1, h2 {
            color: #333;
            text-align: center;
            margin-bottom: 30px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 20px;
            font-size: 14px;
        }
        th, td {
            padding: 12px;
            border-bottom: 1px solid #ddd;
        }
        th {
            background-color: #4CAF50;
            color: white;
            position: sticky;
            top: 0;
            cursor: pointer;
        }
        th:hover {
            background-color: #45a049;
        }
        tr:nth-child(even) {
            background-color: #f2f2f2;
        }
        tr:hover {
            background-color: #e9e9e9;
        }
        .player-name {
            text-align: left;
            font-weight: bold;
            color: #2c3e50;
            min-width: 150px;
            cursor: pointer;
            text-decoration: underline;
        }
        .player-name:hover {
            color: #1a5276;
        }
        .total-column {
            background-color: #e8f5e8;
            font-weight: bold;
        }
        .header-total {
            background-color: #2e7d32;
        }
        .resource-value {
            font-family: 'Courier New', monospace;
            text-align: left !important;
        }
        .summary {
            background-color: #e3f2fd;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 20px;
        }
        .filters {
            background-color: #fff3cd;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 20px;
        }
        .filter-row {
            display: flex;
            gap: 20px;
            margin-bottom: 10px;
            flex-wrap: wrap;
        }
        .filter-group {
            display: flex;
            flex-direction: column;
            min-width: 200px;
        }
        .filter-group label {
            font-weight: bold;
            margin-bottom: 5px;
        }
        .filter-group input {
            padding: 8px;
            border: 1px solid #ddd;
            border-radius: 4px;
        }
        .filter-buttons {
            display: flex;
            gap: 10px;
            margin-top: 10px;
        }
        .filter-buttons button {
            padding: 10px 20px;
            background-color: #4CAF50;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
        }
        .filter-buttons button:hover {
            background-color: #45a049;
        }
        .controls {
            margin-bottom: 20px;
            text-align: center;
        }
        .controls button {
            margin: 5px;
            padding: 8px 15px;
            background-color: #4CAF50;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
        }
        .controls button:hover {
            background-color: #45a049;
        }
        .progress {
            background-color: #ffeb3b;
            padding: 10px;
            border-radius: 5px;
            margin-bottom: 20px;
            text-align: center;
        }
        .modal {
            display: none;
            position: fixed;
            z-index: 1000;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0,0,0,0.5);
        }
        .modal-content {
            background-color: white;
            margin: 5% auto;
            padding: 20px;
            border-radius: 10px;
            width: 90%;
            max-width: 1200px;
            max-height: 80vh;
            overflow-y: auto;
        }
        .close {
            color: #aaa;
            float: right;
            font-size: 28px;
            font-weight: bold;
            cursor: pointer;
        }
        .close:hover {
            color: black;
        }
        .battle-details {
            margin-top: 20px;
        }
        .battle-item {
            border: 1px solid #ddd;
            padding: 10px;
            margin-bottom: 10px;
            border-radius: 5px;
        }
        .battle-header {
            font-weight: bold;
            margin-bottom: 5px;
        }
        .battle-resources {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 5px;
            margin-top: 5px;
        }
        .resource-item {
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .resource-icon {
            width: 16px;
            height: 16px;
            flex-shrink: 0;
        }
        .sort-indicator {
            margin-left: 5px;
            font-size: 12px;
        }
        .table-header {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 5px;
        }
        .resource-header {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 5px;
        }
        /* Новые стили для выравнивания */
        .resource-cell {
            text-align: left !important;
            padding-left: 8px !important;
        }
        .resource-content {
            display: flex;
            align-items: center;
            gap: 6px;
            justify-content: flex-start;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎮 TimeZero Battle Analyzer</h1>
        
        <div class="progress">
            <strong>📊 Статус мониторинга:</strong><br>
            • Обработано боев: {len(self.processed_battles)}<br>
            • Найдено игроков: {len(self.players_resources)}<br>
            • Текущий ID: {self.last_battle_id}<br>
            • Диапазон дат: {min_date.strftime('%d.%m.%Y %H:%M')} - {max_date.strftime('%d.%m.%Y %H:%M')}<br>
            • Последнее обновление: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        </div>
        
        <div class="filters">
            <h3>🔍 Фильтр по дате и времени</h3>
            <div class="filter-row">
                <div class="filter-group">
                    <label for="startDate">Начальная дата:</label>
                    <input type="datetime-local" id="startDate" value="{min_date.strftime('%Y-%m-%dT%H:%M')}">
                </div>
                <div class="filter-group">
                    <label for="endDate">Конечная дата:</label>
                    <input type="datetime-local" id="endDate" value="{max_date.strftime('%Y-%m-%dT%H:%M')}">
                </div>
            </div>
            <div class="filter-buttons">
                <button onclick="applyFilters()">Применить фильтры</button>
                <button onclick="resetFilters()">Сбросить фильтры</button>
                <button onclick="exportData()">Экспорт данных</button>
            </div>
        </div>

        <div class="controls">
            <strong>Быстрая сортировка:</strong>
            <button onclick="sortTable('battles_count', true)">По боям ↓</button>
            <button onclick="sortTable('Total', true)">По общему количеству ↓</button>
            <button onclick="sortTable('Metals', true)">По Metals ↓</button>
            <button onclick="sortTable('Precious metals', true)">По Precious metals ↓</button>
            <button onclick="sortTable('Polymers', true)">По Polymers ↓</button>
            <button onclick="sortTable('Organic', true)">По Organic ↓</button>
            <button onclick="sortTable('Silicon', true)">По Silicon ↓</button>
            <button onclick="sortTable('Radioactive', true)">По Radioactive ↓</button>
            <button onclick="sortTable('Gems', true)">По Gems ↓</button>
            <button onclick="sortTable('Venom', true)">По Venom ↓</button>
            <button onclick="resetSort()">Сбросить сортировку</button>
        </div>
        
        <div class="section">
            <h2>Основные ресурсы</h2>
            <table id="resourcesTable">
                <thead>
                    <tr>
                        <th style="text-align: left" onclick="sortTable('player', false)">Игрок</th>
                        <th onclick="sortTable('battles_count', true)">Боев</th>
                        <th onclick="sortTable('Metals', true)">
                            <div class="resource-header">
                                <img src="{self.resource_icons['Metals']}" class="resource-icon" alt="Metals">
                                Metals
                            </div>
                        </th>
                        <th onclick="sortTable('Precious metals', true)">
                            <div class="resource-header">
                                <img src="{self.resource_icons['Precious metals']}" class="resource-icon" alt="Precious">
                                Precious
                            </div>
                        </th>
                        <th onclick="sortTable('Polymers', true)">
                            <div class="resource-header">
                                <img src="{self.resource_icons['Polymers']}" class="resource-icon" alt="Polymers">
                                Polymers
                            </div>
                        </th>
                        <th onclick="sortTable('Organic', true)">
                            <div class="resource-header">
                                <img src="{self.resource_icons['Organic']}" class="resource-icon" alt="Organic">
                                Organic
                            </div>
                        </th>
                        <th onclick="sortTable('Silicon', true)">
                            <div class="resource-header">
                                <img src="{self.resource_icons['Silicon']}" class="resource-icon" alt="Silicon">
                                Silicon
                            </div>
                        </th>
                        <th onclick="sortTable('Radioactive', true)">
                            <div class="resource-header">
                                <img src="{self.resource_icons['Radioactive']}" class="resource-icon" alt="Radioactive">
                                Radioactive
                            </div>
                        </th>
                        <th onclick="sortTable('Gems', true)">
                            <div class="resource-header">
                                <img src="{self.resource_icons['Gems']}" class="resource-icon" alt="Gems">
                                Gems
                            </div>
                        </th>
                        <th onclick="sortTable('Venom', true)">
                            <div class="resource-header">
                                <img src="{self.resource_icons['Venom']}" class="resource-icon" alt="Venom">
                                Venom
                            </div>
                        </th>
                        <th onclick="sortTable('Total', true)" class="header-total">Всего</th>
                    </tr>
                </thead>
                <tbody id="tableBody">
                    <!-- Данные будут заполнены JavaScript -->
                </tbody>
            </table>
        </div>
    </div>

    <!-- Модальное окно с деталями игрока -->
    <div id="playerModal" class="modal">
        <div class="modal-content">
            <span class="close" onclick="closeModal()">&times;</span>
            <h2 id="modalTitle">Детали боев игрока</h2>
            <div id="playerDetails" class="battle-details">
                <!-- Детали будут заполнены JavaScript -->
            </div>
        </div>
    </div>

    <script>
        // Данные всех игроков
        const allPlayersData = {json.dumps(players_data_js, default=str, ensure_ascii=False)};
        const resourceIcons = {json.dumps(self.resource_icons, ensure_ascii=False)};
        
        let currentPlayersData = {{...allPlayersData}};
        let currentSort = {{ field: 'Total', direction: 'desc' }};

        // Функция для обновления таблицы
        function updateTable() {{
            const tbody = document.getElementById('tableBody');
            tbody.innerHTML = '';
            
            const playersArray = Object.entries(currentPlayersData).sort((a, b) => {{
                const aVal = currentSort.field === 'player' ? a[0] : a[1][currentSort.field];
                const bVal = currentSort.field === 'player' ? b[0] : b[1][currentSort.field];
                
                if (currentSort.field === 'player') {{
                    return currentSort.direction === 'desc' ? 
                        bVal.localeCompare(aVal) : aVal.localeCompare(bVal);
                }} else {{
                    return currentSort.direction === 'desc' ? bVal - aVal : aVal - bVal;
                }}
            }});
            
            playersArray.forEach(([player, data]) => {{
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td class="player-name" onclick="showPlayerDetails('${{player}}')">${{player}}</td>
                    <td class="resource-value">${{data.battles_count}}</td>
                    <td class="resource-cell">
                        <div class="resource-content">
                            <img src="${{resourceIcons.Metals}}" class="resource-icon" alt="Metals">
                            ${{data.Metals.toLocaleString()}}
                        </div>
                    </td>
                    <td class="resource-cell">
                        <div class="resource-content">
                            <img src="${{resourceIcons['Precious metals']}}" class="resource-icon" alt="Precious">
                            ${{data['Precious metals'].toLocaleString()}}
                        </div>
                    </td>
                    <td class="resource-cell">
                        <div class="resource-content">
                            <img src="${{resourceIcons.Polymers}}" class="resource-icon" alt="Polymers">
                            ${{data.Polymers.toLocaleString()}}
                        </div>
                    </td>
                    <td class="resource-cell">
                        <div class="resource-content">
                            <img src="${{resourceIcons.Organic}}" class="resource-icon" alt="Organic">
                            ${{data.Organic.toLocaleString()}}
                        </div>
                    </td>
                    <td class="resource-cell">
                        <div class="resource-content">
                            <img src="${{resourceIcons.Silicon}}" class="resource-icon" alt="Silicon">
                            ${{data.Silicon.toLocaleString()}}
                        </div>
                    </td>
                    <td class="resource-cell">
                        <div class="resource-content">
                            <img src="${{resourceIcons.Radioactive}}" class="resource-icon" alt="Radioactive">
                            ${{data.Radioactive.toLocaleString()}}
                        </div>
                    </td>
                    <td class="resource-cell">
                        <div class="resource-content">
                            <img src="${{resourceIcons.Gems}}" class="resource-icon" alt="Gems">
                            ${{data.Gems.toLocaleString()}}
                        </div>
                    </td>
                    <td class="resource-cell">
                        <div class="resource-content">
                            <img src="${{resourceIcons.Venom}}" class="resource-icon" alt="Venom">
                            ${{data.Venom.toLocaleString()}}
                        </div>
                    </td>
                    <td class="resource-value total-column">${{data.Total.toLocaleString()}}</td>
                `;
                tbody.appendChild(row);
            }});
        }}

        // ... (остальной JavaScript код остается без изменений) ...

        // Инициализация при загрузке
        document.addEventListener('DOMContentLoaded', function() {{
            updateTable();
            // Автообновление каждые 30 секунд
            setTimeout(function() {{
                location.reload();
            }}, 30000);
        }});
    </script>
</body>
</html>"""

    def process_single_battle(self, battle_id):
        """Обрабатывает один бой"""
        filename = None
        try:
            filename, bid, status = self.download_single_battle(battle_id)
            
            if filename and status == "success":
                print(f"✅ Скачан бой {battle_id}")
                
                if self.analyze_single_battle(filename, battle_id):
                    print(f"📊 Проанализирован бой {battle_id}")
                else:
                    print(f"⚠️ Бой {battle_id} не содержит данных")
                
                self.delete_temp_file(filename)
                return True
            else:
                if status != "not_found":
                    print(f"❌ Пропущен бой {battle_id} ({status})")
                return False
                
        except Exception as e:
            print(f"⚠️ Ошибка для боя {battle_id}: {e}")
            if filename:
                self.delete_temp_file(filename)
            return False

    def determine_starting_point(self):
        """Определяет с какого ID начинать мониторинг"""
        start_id = self.find_start_battle_id()
        current_valid_id = self.probe_current_battle_id()
        return current_valid_id

    def monitor_new_battles(self):
        """Основной цикл мониторинга новых боев"""
        current_battle_id = self.determine_starting_point()
        consecutive_failures = 0
        max_consecutive_failures = 100
        
        print(f"🚀 Начинаем мониторинг с ID: {current_battle_id}")
        print("⏹️  Для остановки нажмите Ctrl+C")
        
        while self.is_running and consecutive_failures < max_consecutive_failures:
            self.last_battle_id = current_battle_id
            
            success = self.process_single_battle(current_battle_id)
            
            if success:
                consecutive_failures = 0
                self.save_last_battle_id(current_battle_id)
                
                if len(self.processed_battles) % 10 == 0:
                    self.generate_html_report()
                    print(f"📄 Обновлен отчет после {len(self.processed_battles)} боев")
            else:
                consecutive_failures += 1
                if consecutive_failures > 20:
                    time.sleep(2)
                elif consecutive_failures > 50:
                    time.sleep(5)
            
            current_battle_id += 1
            time.sleep(0.3)
        
        if consecutive_failures >= max_consecutive_failures:
            print("🛑 Достигнут предел неудачных попыток. Перезапустите скрипт.")

    def start_monitoring(self):
        """Запускает мониторинг"""
        try:
            self.cleanup_temp_files()
            self.generate_html_report()
            self.monitor_new_battles()
            
        except KeyboardInterrupt:
            print("🛑 Мониторинг остановлен пользователем")
        except Exception as e:
            print(f"💥 Критическая ошибка: {e}")
        finally:
            self.is_running = False
            self.generate_html_report()
            print(f"💾 Финальный отчет сохранен: {self.html_report}")

def main():
    """Основная функция"""
    print("=" * 60)
    print("🎮 TimeZero Battle Analyzer - Режим реального времени")
    print("=" * 60)
    print("📝 ID боев идут последовательно: 2785756, 2785757, 2785758...")
    print("=" * 60)
    
    analyzer = RealTimeBattleAnalyzer(2785756)
    analyzer.start_monitoring()

if __name__ == "__main__":
    main()
