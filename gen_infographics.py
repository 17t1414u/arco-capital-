import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.patches as patches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from matplotlib.font_manager import FontProperties
import os

# Font setup
FONT_PATH = None
for fp in [
    'C:/Windows/Fonts/NotoSansJP-VF.ttf',
    'C:/Windows/Fonts/msgothic.ttc',
    'C:/Windows/Fonts/meiryo.ttc',
    'C:/Windows/Fonts/BIZ-UDGothicR.ttc',
]:
    if os.path.exists(fp):
        FONT_PATH = fp
        break

def get_fp(size, bold=False):
    if FONT_PATH:
        fp = FontProperties(fname=FONT_PATH, size=size)
        if bold and 'Noto' in FONT_PATH:
            # Try bold variant
            bold_path = FONT_PATH.replace('-VF', 'Bold-VF').replace('-Regular', '-Bold')
            if os.path.exists(bold_path):
                fp = FontProperties(fname=bold_path, size=size, weight='bold')
            else:
                fp = FontProperties(fname=FONT_PATH, size=size, weight='bold')
        elif bold:
            fp = FontProperties(fname=FONT_PATH, size=size, weight='bold')
        return fp
    else:
        return FontProperties(size=size, weight='bold' if bold else 'normal')

SAVE_DIR = r'C:\ai-workspace\stock-company\stock-company\.company\creative\harness\runs\20260410-claude-harness\assets'

BLUE = '#2563EB'
GRAY_TEXT = '#6B7280'
GRAY_BG = '#F3F4F6'
WHITE = '#FFFFFF'
BLACK = '#1F2937'

W, H = 1240/150, 700/150  # inches at 150dpi

# ============================================================
# 1. harness-before-after.png
# ============================================================
def make_before_after():
    fig, ax = plt.subplots(figsize=(W, H), facecolor=WHITE)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 7)
    ax.axis('off')

    # Title
    ax.text(5, 6.55, 'ハーネスなし vs ハーネスあり', ha='center', va='center',
            fontproperties=get_fp(28, bold=True), color=BLACK)
    ax.text(5, 6.05, '設計を変えるだけで、AIの実力が変わる', ha='center', va='center',
            fontproperties=get_fp(14), color=GRAY_TEXT)

    # Divider line
    ax.plot([5, 5], [0.8, 5.7], color='#E5E7EB', lw=1.5, zorder=1)

    # Left column header (gray)
    left_header = FancyBboxPatch((0.3, 4.9), 4.2, 0.65,
                                  boxstyle='round,pad=0.05', linewidth=0,
                                  facecolor=GRAY_BG, zorder=2)
    ax.add_patch(left_header)
    ax.text(2.4, 5.225, 'ハーネスなし', ha='center', va='center',
            fontproperties=get_fp(18, bold=True), color=GRAY_TEXT)

    # Right column header (blue)
    right_header = FancyBboxPatch((5.5, 4.9), 4.2, 0.65,
                                   boxstyle='round,pad=0.05', linewidth=0,
                                   facecolor=BLUE, zorder=2)
    ax.add_patch(right_header)
    ax.text(7.6, 5.225, 'ハーネスあり', ha='center', va='center',
            fontproperties=get_fp(18, bold=True), color=WHITE)

    # Items
    left_items = ['「狩猟型」', '毎回ゼロから指示', '結果にバラつき', 'スキルに依存']
    right_items = ['「農耕型」', '一度作れば自律稼働', '出力が安定', '仕組みに依存']

    y_positions = [4.25, 3.45, 2.65, 1.85]

    for i, (li, ri) in enumerate(zip(left_items, right_items)):
        y = y_positions[i]
        # Left item box
        lb = FancyBboxPatch((0.3, y - 0.3), 4.2, 0.6,
                             boxstyle='round,pad=0.05', linewidth=1,
                             edgecolor='#E5E7EB', facecolor=GRAY_BG, zorder=2)
        ax.add_patch(lb)
        ax.text(2.4, y, li, ha='center', va='center',
                fontproperties=get_fp(14), color=GRAY_TEXT)

        # Right item box
        rb = FancyBboxPatch((5.5, y - 0.3), 4.2, 0.6,
                             boxstyle='round,pad=0.05', linewidth=1.5,
                             edgecolor=BLUE, facecolor=WHITE, zorder=2)
        ax.add_patch(rb)
        ax.text(7.6, y, ri, ha='center', va='center',
                fontproperties=get_fp(14, bold=(i==0)), color=BLUE if i==0 else BLACK)

    # Bottom arrow + text
    arrow = FancyArrowPatch((1.5, 0.65), (8.5, 0.65),
                             arrowstyle='->', color=BLUE,
                             mutation_scale=18, lw=2)
    ax.add_patch(arrow)
    ax.text(5, 0.65, 'プロンプトを磨く  →  仕組みを設計する', ha='center', va='center',
            fontproperties=get_fp(13, bold=True), color=BLUE,
            bbox=dict(boxstyle='round,pad=0.3', facecolor=WHITE, edgecolor=WHITE))

    outpath = os.path.join(SAVE_DIR, 'harness-before-after.png')
    fig.savefig(outpath, dpi=150, bbox_inches='tight', facecolor=WHITE)
    plt.close(fig)
    size_kb = os.path.getsize(outpath) / 1024
    print(f'harness-before-after.png: {size_kb:.1f} KB')


# ============================================================
# 2. harness-3files.png
# ============================================================
def make_3files():
    fig, ax = plt.subplots(figsize=(W, H), facecolor=WHITE)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 7)
    ax.axis('off')

    # Title
    ax.text(5, 6.55, '3ファイルで Claude Code が変わる', ha='center', va='center',
            fontproperties=get_fp(28, bold=True), color=BLACK)
    ax.text(5, 6.05, 'ハーネス設計の最小構成', ha='center', va='center',
            fontproperties=get_fp(14), color=GRAY_TEXT)

    # Center node
    center_circle = plt.Circle((5, 3.2), 1.05, color=BLUE, zorder=3)
    ax.add_patch(center_circle)
    ax.text(5, 3.35, 'Claude Code', ha='center', va='center',
            fontproperties=get_fp(13, bold=True), color=WHITE, zorder=4)
    ax.text(5, 3.0, '（別人格）', ha='center', va='center',
            fontproperties=get_fp(11), color=WHITE, zorder=4)

    # Spokes data: (x, y, title, subtitle, angle_deg)
    spokes = [
        (1.4, 5.0, 'CLAUDE.md', '記憶・行動指針'),
        (1.4, 1.5, 'settings.json', '自動ガード'),
        (8.6, 3.2, '.claude/skills/', '専門手順書'),
    ]

    spoke_ends_center = [(3.95, 4.15), (3.95, 2.25), (6.05, 3.2)]

    for (x, y, title, subtitle), (cx, cy) in zip(spokes, spoke_ends_center):
        # Line from box edge toward center
        ax.annotate('', xy=(cx, cy), xytext=(x + (0.9 if x < 5 else -0.9), y),
                    arrowprops=dict(arrowstyle='->', color=BLUE, lw=2,
                                    mutation_scale=15))

        # Box
        bw, bh = 2.4, 1.0
        bx = x - bw/2
        by = y - bh/2
        box = FancyBboxPatch((bx, by), bw, bh,
                              boxstyle='round,pad=0.08', linewidth=2,
                              edgecolor=BLUE, facecolor=GRAY_BG, zorder=3)
        ax.add_patch(box)
        ax.text(x, y + 0.18, title, ha='center', va='center',
                fontproperties=get_fp(15, bold=True), color=BLUE, zorder=4)
        ax.text(x, y - 0.2, subtitle, ha='center', va='center',
                fontproperties=get_fp(12), color=GRAY_TEXT, zorder=4)

    outpath = os.path.join(SAVE_DIR, 'harness-3files.png')
    fig.savefig(outpath, dpi=150, bbox_inches='tight', facecolor=WHITE)
    plt.close(fig)
    size_kb = os.path.getsize(outpath) / 1024
    print(f'harness-3files.png: {size_kb:.1f} KB')


# ============================================================
# 3. swe-bench-comparison.png
# ============================================================
def make_swe_bench():
    fig, ax = plt.subplots(figsize=(W, H), facecolor=WHITE)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 7)
    ax.axis('off')

    # Title
    ax.text(5, 6.55, 'ハーネス設計で 22 ポイント差', ha='center', va='center',
            fontproperties=get_fp(28, bold=True), color=BLACK)
    ax.text(5, 6.05, 'モデルを変えるより、設計を変えろ', ha='center', va='center',
            fontproperties=get_fp(14), color=GRAY_TEXT)

    # 3 blocks
    blocks = [
        (1.5, '22pt', BLUE, 'ハーネス設計の差'),
        (5.0, '1pt', GRAY_TEXT, 'モデル性能の差'),
        (8.5, 'SWE-\nbench', BLACK, 'コーディング能力評価指標'),
    ]

    for cx, big_text, big_color, label in blocks:
        bw, bh = 2.6, 3.8
        bx = cx - bw/2
        by = 1.5
        # box
        box = FancyBboxPatch((bx, by), bw, bh,
                              boxstyle='round,pad=0.05', linewidth=0,
                              facecolor=GRAY_BG, zorder=2)
        ax.add_patch(box)
        # top accent bar
        accent = FancyBboxPatch((bx, by + bh - 0.28), bw, 0.28,
                                 boxstyle='round,pad=0.0', linewidth=0,
                                 facecolor=BLUE, zorder=3)
        ax.add_patch(accent)
        # big number
        is_swe = '\n' in big_text
        fs = 52 if not is_swe else 36
        ax.text(cx, by + bh/2 + 0.2, big_text, ha='center', va='center',
                fontproperties=get_fp(fs, bold=True), color=big_color, zorder=4)
        # label
        ax.text(cx, by + 0.45, label, ha='center', va='center',
                fontproperties=get_fp(13), color=GRAY_TEXT, zorder=4)

    # Bottom emphasis
    emph = FancyBboxPatch((1.0, 0.2), 8.0, 0.85,
                           boxstyle='round,pad=0.05', linewidth=2,
                           edgecolor=BLUE, facecolor=WHITE, zorder=2)
    ax.add_patch(emph)
    ax.text(5, 0.625, '同じモデルでも、ハーネス次第で 22 倍の差', ha='center', va='center',
            fontproperties=get_fp(14, bold=True), color=BLUE, zorder=3)

    outpath = os.path.join(SAVE_DIR, 'swe-bench-comparison.png')
    fig.savefig(outpath, dpi=150, bbox_inches='tight', facecolor=WHITE)
    plt.close(fig)
    size_kb = os.path.getsize(outpath) / 1024
    print(f'swe-bench-comparison.png: {size_kb:.1f} KB')


# ============================================================
# 4. langchain-improvement.png
# ============================================================
def make_langchain():
    fig, ax = plt.subplots(figsize=(W, H), facecolor=WHITE)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 7)
    ax.axis('off')

    # Title
    ax.text(5, 6.55, 'LangChain 実証：+13.7pt 改善', ha='center', va='center',
            fontproperties=get_fp(28, bold=True), color=BLACK)
    ax.text(5, 6.05, 'モデル変更ゼロ、ハーネス設計のみで達成', ha='center', va='center',
            fontproperties=get_fp(14), color=GRAY_TEXT)

    # Left block: before
    bw, bh = 2.8, 3.4
    # Before box
    before_box = FancyBboxPatch((0.4, 1.8), bw, bh,
                                 boxstyle='round,pad=0.05', linewidth=0,
                                 facecolor=GRAY_BG, zorder=2)
    ax.add_patch(before_box)
    ax.text(0.4 + bw/2, 1.8 + bh/2 + 0.35, '52.8%', ha='center', va='center',
            fontproperties=get_fp(56, bold=True), color=GRAY_TEXT, zorder=3)
    ax.text(0.4 + bw/2, 1.8 + 0.5, 'ハーネス改善前', ha='center', va='center',
            fontproperties=get_fp(14), color=GRAY_TEXT, zorder=3)

    # Right block: after
    after_box = FancyBboxPatch((6.8, 1.8), bw, bh,
                                boxstyle='round,pad=0.05', linewidth=2,
                                edgecolor=BLUE, facecolor=WHITE, zorder=2)
    ax.add_patch(after_box)
    # top accent
    after_accent = FancyBboxPatch((6.8, 1.8 + bh - 0.28), bw, 0.28,
                                   boxstyle='round,pad=0.0', linewidth=0,
                                   facecolor=BLUE, zorder=3)
    ax.add_patch(after_accent)
    ax.text(6.8 + bw/2, 1.8 + bh/2 + 0.35, '66.5%', ha='center', va='center',
            fontproperties=get_fp(56, bold=True), color=BLUE, zorder=3)
    ax.text(6.8 + bw/2, 1.8 + 0.5, 'ハーネス改善後', ha='center', va='center',
            fontproperties=get_fp(14), color=BLUE, zorder=3)

    # Center arrow + label
    arrow = FancyArrowPatch((3.5, 3.5), (6.5, 3.5),
                             arrowstyle='->', color=BLUE,
                             mutation_scale=30, lw=3, zorder=4)
    ax.add_patch(arrow)
    ax.text(5, 4.0, 'ハーネス設計改善', ha='center', va='center',
            fontproperties=get_fp(13, bold=True), color=BLUE, zorder=4)

    # Bottom emphasis box
    emph = FancyBboxPatch((3.0, 0.2), 4.0, 1.1,
                           boxstyle='round,pad=0.08', linewidth=2.5,
                           edgecolor=BLUE, facecolor=WHITE, zorder=2)
    ax.add_patch(emph)
    ax.text(5, 0.85, '+13.7pt ↑', ha='center', va='center',
            fontproperties=get_fp(26, bold=True), color=BLUE, zorder=3)
    ax.text(5, 0.38, '改善幅', ha='center', va='center',
            fontproperties=get_fp(12), color=GRAY_TEXT, zorder=3)

    outpath = os.path.join(SAVE_DIR, 'langchain-improvement.png')
    fig.savefig(outpath, dpi=150, bbox_inches='tight', facecolor=WHITE)
    plt.close(fig)
    size_kb = os.path.getsize(outpath) / 1024
    print(f'langchain-improvement.png: {size_kb:.1f} KB')


make_before_after()
make_3files()
make_swe_bench()
make_langchain()
print('Done.')
