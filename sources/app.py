from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import sys
import datetime
import json
import shutil
import logging

# ---------- 环境 ----------
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, PROJECT_ROOT)

from config import OUTPUT_DIR, WEIGHT_FILE
from query_residential import query_by_id, query_by_name, query_by_coordinates
from get_single_residential_poi_fixed import main as get_poi
from generate_report_fixed import generate_markdown_report, markdown_to_html
from utils.file.weight_loader import load_weight_config
from utils.poi.poi_analysis import calculate_weighted_score

app = Flask(__name__)
CORS(app)

# 配置日志
logging.basicConfig(level=logging.DEBUG)
app.logger.setLevel(logging.DEBUG)

# ---------- 工具：权重文件自动搜索 ----------
def find_weight_csv():
    custom = os.path.join(PROJECT_ROOT, 'data', 'poi_weights', '高德POI_加权.csv')
    if os.path.exists(custom):
        return custom
    default = os.path.join(PROJECT_ROOT, 'config', 'poi_weight.csv')
    if os.path.exists(default):
        return default
    raise FileNotFoundError(f'未找到任何权重文件，已搜索：{custom} 和 {default}')

# ---------- 查询 ----------
@app.route('/query', methods=['POST'])
def query():
    data = request.get_json() or {}
    method = data.get('method')
    try:
        if method == 'id':
            result = query_by_id(data['id'])
        elif method == 'name':
            result = query_by_name(data['name'])
        elif method == 'coord':
            result = query_by_coordinates(data['lng'], data['lat'])
        else:
            return jsonify({'error': '无效查询方式'}), 400
        return jsonify({'result': result})
    except Exception as e:
        app.logger.error(f"查询错误: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

# ---------- POI ----------
@app.route('/poi', methods=['POST'])
def poi():
    data = request.get_json() or {}
    rid = data['residential_id']
    radius = data.get('radius', 1200)
    filter_poi = data.get('filter_poi', True)
    threshold = data.get('threshold', 0.4)
    try:
        import get_single_residential_poi_fixed as poi_mod
        poi_mod.RADIUS = radius
        poi_mod.FILTER_LOW_WEIGHT_POI = filter_poi
        poi_mod.POI_WEIGHT_THRESHOLD = threshold
        get_poi(residential_id=rid,
                name=data.get('name'),
                address=data.get('address'))

        poi_unique = os.path.join(OUTPUT_DIR, 'poi', f'poi_{rid}_unique.csv')
        poi_raw = os.path.join(OUTPUT_DIR, 'poi', f'poi_{rid}.csv')
        poi_file = poi_unique if os.path.exists(poi_unique) else poi_raw
        if not os.path.exists(poi_file):
            return jsonify({'error': f'POI 文件不存在: {poi_file}'}), 404
        return jsonify({'poi_file': poi_file})
    except Exception as e:
        app.logger.error(f"POI处理错误: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

# ---------- 评分 ----------
@app.route('/score', methods=['POST'])
def score():
    data = request.get_json() or {}
    poi_file = data.get('poi_file')
    if not poi_file or not os.path.exists(poi_file):
        return jsonify({'error': f'缺少 POI 文件: {poi_file}'}), 404
    try:
        weight_csv = find_weight_csv()
        weight_map = load_weight_config(weight_csv)
        total, cnt, df = calculate_weighted_score(poi_file, weight_map)
        return jsonify({
            'total_score': total,
            'poi_count': cnt,
            'categories': df.to_dict('records')
        })
    except Exception as e:
        app.logger.error(f"评分错误: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

# ---------- 报告 ----------
@app.route('/report', methods=['POST'])
def report():
    data = request.get_json() or {}
    rid = data.get('residential_id')
    stats_dir = data.get('stats_dir')
    if not rid or not stats_dir:
        return jsonify({'error': '缺少 residential_id 或 stats_dir'}), 400
    try:
        md_path = os.path.join(stats_dir, f'{rid}_评估报告.md')
        html_path = md_path.replace('.md', '.html')
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(generate_markdown_report(rid, stats_dir))
        markdown_to_html(md_path, html_path)
        return jsonify({'markdown': md_path, 'html': html_path})
    except Exception as e:
        app.logger.error(f"报告生成错误: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

# ---------- 一键落盘 + 下载 ----------
SAVE_ROOT = os.path.join(PROJECT_ROOT, 'output', 'web_save')

@app.route('/save', methods=['POST'])
def save_all():
    try:
        # 1. 多重 JSON 解析保护
        app.logger.debug("开始处理保存请求")
        
        data = request.get_json()
        app.logger.debug(f"初始数据: {data}, 类型: {type(data)}")
        
        # 如果 data 是字符串，尝试解析多次
        parse_count = 0
        while isinstance(data, str) and parse_count < 3:
            try:
                data = json.loads(data)
                parse_count += 1
                app.logger.debug(f"第{parse_count}次解析后: {data}, 类型: {type(data)}")
            except json.JSONDecodeError:
                app.logger.warning("无法进一步解析JSON字符串")
                break
        
        # 2. 如果最终还不是字典，返回错误
        if not isinstance(data, dict):
            app.logger.error(f"无效的数据类型: {type(data)}, 数据: {data}")
            return jsonify({'error': f'无效的请求数据格式，期望 JSON 对象，得到 {type(data)}'}), 400
        
        # 3. 强制类型转换
        app.logger.debug("开始类型转换")
        try:
            rid = str(data['residential_id'])
            name = str(data.get('name', rid))
            radius = int(data.get('radius', 1200))
            threshold = float(data.get('threshold', 0.4))
            filter_poi = bool(data.get('filter_poi', True))
            
            # 处理可能的空值
            lng = None
            lat = None
            if data.get('lng') is not None:
                lng = float(data['lng'])
            if data.get('lat') is not None:
                lat = float(data['lat'])
                
        except (ValueError, TypeError, KeyError) as e:
            app.logger.error(f"参数解析错误: {e}, 数据: {data}")
            return jsonify({'error': f'参数类型错误: {e}'}), 400

        app.logger.debug(f"转换后参数: rid={rid}, name={name}, radius={radius}, threshold={threshold}")

        # 4. 目录 & 时间戳
        ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        save_dir = os.path.join(SAVE_ROOT, f'{rid}_{ts}')
        os.makedirs(save_dir, exist_ok=True)
        app.logger.debug(f"创建保存目录: {save_dir}")

        # 5. 拉 POI（去重）
        app.logger.debug("开始获取POI数据")
        import get_single_residential_poi_fixed as poi_mod
        poi_mod.RADIUS = radius
        poi_mod.POI_WEIGHT_THRESHOLD = threshold
        poi_mod.FILTER_LOW_WEIGHT_POI = filter_poi
        
        get_poi(residential_id=rid, name=name, address=data.get('address'))

        poi_unique = os.path.join(OUTPUT_DIR, 'poi', f'poi_{rid}_unique.csv')
        poi_raw = os.path.join(OUTPUT_DIR, 'poi', f'poi_{rid}.csv')
        poi_file = poi_unique if os.path.exists(poi_unique) else poi_raw
        
        if not os.path.exists(poi_file):
            app.logger.error(f"POI文件不存在: {poi_file}")
            return jsonify({'error': f'POI 文件不存在: {poi_file}'}), 404
        
        # 复制POI文件到保存目录
        shutil.copy(poi_file, os.path.join(save_dir, os.path.basename(poi_file)))
        app.logger.debug("POI文件复制完成")

        # 6. 评分（强制用去重）
        app.logger.debug("开始计算评分")
        weight_csv = find_weight_csv()
        weight_map = load_weight_config(weight_csv)
        total_score, poi_cnt, cate_df = calculate_weighted_score(poi_file, weight_map)

        score_csv = os.path.join(save_dir, f'score_{rid}.csv')
        cate_df.to_csv(score_csv, index=False, encoding='utf-8-sig')
        app.logger.debug("评分计算完成")

        # 7. 各种 JSON（报告模板需要）
        summary = {
            'residential_id': rid,
            'total_score': float(total_score),
            'poi_count': int(poi_cnt),
            'timestamp': datetime.datetime.now().isoformat()
        }
        with open(os.path.join(save_dir, 'summary.json'), 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

        # 生成与 generate_report_fixed.py 兼容的 stats 格式
        # 将大、中、小类数据合并为一个列表，每个项目包含"类型"字段
        stats_list = []

        # 添加大类数据
        big_data = cate_df[cate_df['类型'] == '大类'].to_dict('records')
        for item in big_data:
            item_with_type = item.copy()
            item_with_type['类型'] = '大类'  # 确保有类型字段
            stats_list.append(item_with_type)

        # 添加中类数据  
        mid_data = cate_df[cate_df['类型'] == '中类'].to_dict('records')
        for item in mid_data:
            item_with_type = item.copy()
            item_with_type['类型'] = '中类'  # 确保有类型字段
            stats_list.append(item_with_type)

        # 添加小类数据
        small_data = cate_df[cate_df['类型'] == '小类'].to_dict('records')
        for item in small_data:
            item_with_type = item.copy()
            item_with_type['类型'] = '小类'  # 确保有类型字段
            stats_list.append(item_with_type)

        # 保存为列表格式（generate_report_fixed.py 期望的格式）
        with open(os.path.join(save_dir, f'stats_{rid}.json'), 'w', encoding='utf-8') as f:
            json.dump(stats_list, f, ensure_ascii=False, indent=2)

        app.logger.debug("JSON文件生成完成")

        # 8. 生成报告
        app.logger.debug("开始生成报告")
        md_path = os.path.join(save_dir, f'{name}_评估报告.md')
        html_path = md_path.replace('.md', '.html')
        
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(generate_markdown_report(rid, save_dir, name))
        markdown_to_html(md_path, html_path)
        app.logger.debug("报告生成完成")

        return jsonify({
            'save_dir': save_dir,
            'markdown_url': f'/download/{rid}_{ts}/{name}_评估报告.md',
            'html_url': f'/download/{rid}_{ts}/{name}_评估报告.html'
        })
        
    except Exception as e:
        app.logger.error(f"保存过程中出错: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/download/<path:subpath>/<filename>')
def download(subpath, filename):
    dir_path = os.path.join(SAVE_ROOT, subpath)
    return send_from_directory(dir_path, filename, as_attachment=True)


if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=8000)