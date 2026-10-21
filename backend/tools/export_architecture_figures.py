"""Export code-grounded, editable engineering diagrams without reading patient data or credentials."""
import argparse,ast,hashlib,json
from datetime import datetime,timezone,timedelta
from pathlib import Path
from xml.sax.saxutils import escape
ROOT=Path(__file__).resolve().parents[2]
COLORS={'ink':'#17283e','muted':'#52677e','blue':'#16649c','green':'#176957','orange':'#a85b0b'}
class SVG:
 def __init__(self,title,subtitle,w=1800,h=1120):
  self.w,self.h=w,h;self.a=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img"><title>{escape(title)}</title><defs><marker id="arrow" markerWidth="9" markerHeight="9" refX="8" refY="4.5" orient="auto-start-reverse"><path d="M0,0 L9,4.5 L0,9 Z" fill="#52677e"/></marker><marker id="warn" markerWidth="9" markerHeight="9" refX="8" refY="4.5" orient="auto"><path d="M0,0 L9,4.5 L0,9 Z" fill="#a85b0b"/></marker></defs><style>text{{font-family:"Microsoft YaHei","Noto Sans CJK SC",sans-serif;fill:#17283e}}.title{{font-size:36px;font-weight:700}}.sub{{font-size:22px;fill:#52677e}}.box-title{{font-size:24px;font-weight:700}}.body{{font-size:21px}}.note{{font-size:20px;fill:#52677e}}</style><rect width="100%" height="100%" fill="white"/>']
  self.text(60,65,title,'title');self.text(60,108,subtitle,'sub')
 def text(self,x,y,t,cls='body',parent=None):
  attr=f' data-box="{parent}"' if parent else ''
  self.a.append(f'<text x="{x}" y="{y}" class="{cls}"{attr}>{escape(t)}</text>')
 def box(self,key,x,y,w,h,title,lines,color='blue',fill='#f0f6fb'):
  self.a.append(f'<g><rect id="{key}" x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="{fill}" stroke="{COLORS[color]}" stroke-width="2"/>')
  self.text(x+22,y+40,title,'box-title',key)
  for i,line in enumerate(lines):self.text(x+22,y+78+i*32,line,'body',key)
  self.a.append('</g>')
 def path(self,d,label=None,x=0,y=0,warn=False):
  color=COLORS['orange' if warn else 'muted'];dash=' stroke-dasharray="10 7"' if warn else ''
  self.a.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="2.3" marker-end="url(#{"warn" if warn else "arrow"})"{dash}/>')
  if label:self.text(x,y,label,'note')
 def save(self,path):path.write_text(''.join(self.a)+'</svg>',encoding='utf-8')
def check_source():
 declarations={}
 for rel in ['backend/app/models/pacs.py','backend/app/models/dicom_measurement.py','backend/app/models/dicom_view_state.py','backend/app/models/dicom_review.py','backend/app/models/doctor_opinion.py']:
  tree=ast.parse((ROOT/rel).read_text(encoding='utf-8-sig'))
  for cls in [n for n in tree.body if isinstance(n,ast.ClassDef)]:
   attrs={n.targets[0].id:n.value for n in cls.body if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name)}
   if '__tablename__' not in attrs:continue
   table=ast.literal_eval(attrs['__tablename__']);fk=attrs.get('case_id')
   assert fk is not None and any(isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='ForeignKey' and ast.literal_eval(n.args[0])=='cases.id' for n in ast.walk(fk)),table
   declarations[table]=sorted(attrs)
 assert set(declarations)=={'pacs_study_links','dicom_world_measurements','dicom_view_states','dicom_reading_reviews','doctor_opinions'}
 assert 'snapshot_json' in declarations['dicom_reading_reviews']
 api=(ROOT/'backend/app/api/pacs.py').read_text(encoding='utf-8-sig')
 assert 'identity: dict=Depends(require_doctor)' in api
 return declarations

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
 out=args.output.resolve();assert out.drive.upper()=='E:' and not out.exists(),'A fresh E-drive output is required'
 declarations=check_source();out.mkdir(parents=True)
 date=datetime.now(timezone(timedelta(hours=8))).date().isoformat()
 g=SVG('BrainFusion AI · 当前系统架构',f'{date}工程材料 | 实线为已实现主路径；虚线为真实端到端尚未接通的分支',1800,1160)
 g.text(60,160,'受支持 NIfTI 路径','sub')
 g.box('nifti',60,185,300,155,'四序列 NIfTI',['T1c / T1n / T2w / FLAIR','原网格契约与来源核对'])
 g.box('ai',450,185,355,155,'FastAPI / 现有 AI',['固定 MONAI 真实分割','自动掩膜特征与研究预测'])
 g.box('outputs',910,185,355,155,'版本与文件产物',['MRI / 原分割只读 mask','输入、模型与分析来源'])
 g.box('viewn',1370,185,365,155,'Vue3 / Cornerstone3D',['同一现有工作站入口','三视图、四序列与工具'])
 for x1,x2 in [(360,450),(805,910),(1265,1370)]:g.path(f'M{x1},262 H{x2}')
 g.text(60,430,'受支持 DICOM 路径','sub')
 g.box('dicom',60,455,300,170,'获准公开经典 MR',['来源与像素复核证据','受控准备、登记及导入','非任意上传 / 自动脱敏'])
 g.box('orthanc',450,455,355,170,'本机 Orthanc',['DICOMweb / 实例归档','Study / Series / Instance','凭据仅后端持有'])
 g.box('proxy',910,455,355,170,'后端核对与鉴权代理',['UID 显式病例关联','元数据、几何与来源版本','导入回执持久化'])
 g.box('viewd',1370,455,365,170,'同一 Cornerstone 工作站',['真实 DICOM 三视图','LPS 毫米距离 / 视图','本分支尚无模型分割'])
 for x1,x2 in [(360,450),(805,910),(1265,1370)]:g.path(f'M{x1},540 H{x2}')
 g.path('M628,455 V380 H815 V315 H805','匹配真实四序列 / 转换登记与模型激活：受阻',840,397,True)
 g.box('account',60,820,300,200,'本机复核账户',['私有配置 / 盐化摘要','doctor 角色与会话','仅约束 DICOM 复核','不等于医师资质'],color='green',fill='#f0f8f4')
 g.box('db',450,820,355,200,'SQLite 业务库',['当前 17 表','距离 / 视图 / 复核快照','结果与分析版本关联','病例意见保持独立'])
 g.box('backup',910,820,355,200,'联合恢复边界',['归档索引与原实例','业务库、产物与模型来源','登记 / 回执 / 账户配置','须实际独立恢复验证'])
 g.box('report',1370,820,365,200,'现有报告页 / PDF',['来源与内容版本核对','本地账户复核 / 历史','导出前后再次核对','教学研究，不作临床诊断'])
 g.path('M1552,625 V820','同一报告入口',1575,722)
 g.path('M1460,625 V708 H628 V820','测量 / 视图 / 复核持久化',730,698)
 g.path('M805,935 H850 V1040 H1552 V1020','报告读取业务版本；备份范围还包含库外文件',900,1075)
 g.path('M360,910 H450','复核身份',365,894)
 g.text(60,1140,'研究 IDH 仅解释原始目标值；单序列阅片不要求 IDH 标签。Docker / 异机交付与真实四序列桥未通过。','note')
 g.save(out/'architecture-current.svg')
 e=SVG('BrainFusion AI · DICOM 数据关系与来源绑定',f'{date}工程材料 | 17 张业务表中的 DICOM 子图；不是全库 ER 图',1800,1170)
 e.box('archive',60,175,460,180,'Orthanc（库外归档）',['Study / Series / Instance UID','DICOM 原文件与归档索引','不存于业务 SQL 实例表'])
 e.box('links',650,175,480,180,'pacs_study_links',['case_id → cases.id（声明外键）','archive_id / Study UID','归档指纹与元数据快照'])
 e.box('cases',1320,175,420,180,'cases / 病例',['业务病例 ID','病例与归档显式关联','单病例可有多条检查关联'])
 e.path('M1320,263 H1130','1 → 多（声明）',1140,246)
 e.path('M520,263 H650','UID / 来源',530,246,True)
 e.box('context',650,435,480,175,'运行时来源上下文',['病例检查关联 ID / 归档指纹','Study / Series / FrameOfReference','元数据 SHA-256（非逐次像素全哈希）'],color='green',fill='#f0f8f4')
 e.path('M890,355 V435','每次核对',910,402,True)
 e.box('opinion',1320,435,420,175,'doctor_opinions',['case_id → cases.id（唯一）','病例级独立意见','不等于本序列人工复核'])
 e.path('M1530,355 V435','0 或 1',1555,402)
 e.box('measure',60,760,460,185,'dicom_world_measurements',['case_id / Study / Series UID','context_json / 患者 LPS 端点','length_mm / 不可变 client_uid','旧来源记录保留但不当当前'])
 e.box('views',650,760,480,185,'dicom_view_states',['case_id / Study / Series UID','context_json / state_json','三相机与窗值 / 不可变版本','当前来源一致时才恢复'])
 e.box('reviews',1320,760,420,185,'dicom_reading_reviews',['case_id / 来源与内容 SHA','snapshot_json（含 review_actor）','署名 / 意见 / 复核状态','内容变更后历史仍可追溯'])
 e.path('M750,610 V665 H290 V760',warn=True);e.path('M890,610 V760',warn=True);e.path('M1030,610 V665 H1530 V760',warn=True)
 e.path('M1660,355 H1770 V710 H180 V760','case_id 声明关联（各子表）',1320,697)
 e.path('M1070,710 V760');e.path('M1710,710 V760')
 e.text(60,1030,'实线：SQLAlchemy 声明的病例关系；同类记录均声明 case_id → cases.id，不据此声称 SQLite 强制外键已开启。','note')
 e.text(60,1070,'虚线：服务端逻辑核对或库外绑定，不是 SQL 外键。复核内容 SHA 不含复核本身，导出 SHA 含最新复核状态。','note')
 e.text(60,1110,'本地账户存在私有 LOCAL_AUTH_FILE；仅将 actor 写入复核快照。账户不是 SQL 表，会话不备份、不证明医师资质。','note')
 e.text(60,1150,'联合恢复还需原实例、索引、导入来源 / 回执、账户与运行路径；只复制 SQLite 不构成完整系统恢复。','note')
 e.save(out/'dicom-data-relations.svg')
 sources=['backend/app/models/pacs.py','backend/app/models/dicom_measurement.py','backend/app/models/dicom_view_state.py','backend/app/models/dicom_review.py','backend/app/models/doctor_opinion.py','backend/app/api/pacs.py','backend/app/services/dicom_review.py','backend/app/services/local_auth.py','backend/tools/snapshot_pacs_joint.py','frontend/src/components/mri/CornerstoneViewer.vue','frontend/src/views/Report.vue']
 record={'format':'engineering-architecture-figures-v1','date_beijing':date,'scope':'Current implementation and evidence boundaries, not clinical/research performance','declared_case_relationships':declarations,'source_sha256':{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in sources},'outputs':[{'file':n,'sha256':hashlib.sha256((out/n).read_bytes()).hexdigest()} for n in ['architecture-current.svg','dicom-data-relations.svg']]}
 (out/'source-manifest.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({'status':'passed','output':str(out),'figures':2}))
if __name__=='__main__':main()
