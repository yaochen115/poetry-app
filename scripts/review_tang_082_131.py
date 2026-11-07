"""Apply the explicitly edited first Tang review; preserves previous drafts.

This is a finite editorial decision list, not an automatic approval generator.
Original text and production data are never changed here.
"""
import copy
import json
import sys
from pathlib import Path
from enrichment_pipeline import Pipeline, digest, validate_patch, write_once, read

EDITS = {
    'tang-082': {
        'notes': [
            {'term': '解', 'meaning': '能、能够，读 jiě；“解落”意为能够使树叶落下。'},
            {'term': '三秋', 'meaning': '秋季，这里通常解作晚秋。'},
            {'term': '二月', 'meaning': '农历二月，春季。'},
            {'term': '千尺', 'meaning': '形容浪高，是夸张写法；下句“万竿”也极言数量多。'},
        ]},
    'tang-083': {'translation': '黄师塔前，江水向东流去；春光使人慵懒困倦，我倚着和暖的微风赏花。一丛无人照管的桃花开得正盛，到底是深红的惹人喜爱，还是浅红的惹人喜爱呢？'},
    'tang-088': {
        'translation': '玉粒般的桂子纷纷从月亮那边落下来，在寺殿前拾起，露光显得清新润泽。直到如今，我也不明白天上的事情；这大概是嫦娥抛下来送给人间的吧。',
        'notes': [
            {'term': '玉颗', 'meaning': '像玉粒一样的桂子，是诗中的比喻。'},
            {'term': '珊珊', 'meaning': '叠词，写桂子纷纷落下的情态，联系玉颗落下的声音。'},
            {'term': '月轮', 'meaning': '圆月；诗中把桂子的飘落想象为从月宫落下。'},
            {'term': '露华', 'meaning': '露水的光泽。'},
            {'term': '不会', 'meaning': '不明白，不理解。'},
            {'term': '掷与', 'meaning': '抛给；“与”是给的意思。'},
        ]},
    'tang-089': {
        'translation': '绿树的阴影浓密，夏日显得格外悠长，楼台的倒影映入池塘。微风吹起，水面像晶莹的帘幕一样轻轻摇动；满架蔷薇盛开，使整个庭院都弥漫着花香。',
        'notes': [
            {'term': '阴浓', 'meaning': '树荫浓密。'},
            {'term': '倒影', 'meaning': '楼台映在水中的影像。'},
            {'term': '水晶帘', 'meaning': '通行赏析以晶莹的帘幕比喻波光荡漾的池面；也有实指帘子的解释。'},
            {'term': '蔷薇', 'meaning': '蔓生灌木，枝条可攀上花架，花有香气。'},
        ]},
    'tang-091': {
        'translation': '小孩子撑着小船，偷偷采了白莲的莲蓬回来。他不知道掩藏自己的行踪，船过后，水面浮萍分开的一道痕迹便显露出来。',
        'notes': [
            {'term': '小艇', 'meaning': '小船。'},
            {'term': '偷采', 'meaning': '瞒着别人偷偷采摘，写孩子的天真顽皮。'},
            {'term': '白莲', 'meaning': '白莲，采摘之物通常解为白莲的莲蓬。'},
            {'term': '不解', 'meaning': '不懂得，不知道。'},
            {'term': '浮萍', 'meaning': '漂浮在水面的植物；小船划过，浮萍便向两旁分开。'},
        ]},
    'tang-092': {'translation': '天色已晚，青苍的山岭显得遥远；天气寒冷，简陋的茅屋更显清贫。柴门边传来狗叫声，风雪之夜，有人归来了。'},
    'tang-093': {'translation': '旅馆里寒灯孤照，我独自难以入睡；客居他乡的心情，为何愈加凄凉？今夜故乡的亲人想必正在思念千里之外的我；到了明天，我这两鬓如霜的人又添了一岁。'},
    'tang-098': {
        'translation': '诸葛亮在三国鼎立的局面中建立了卓越功业，又因创制八阵图而成名。江水奔流，布阵的石头仍未移转；令人长久遗憾的是，刘备企图吞吴却失策败亡。',
        'notes': [
            {'term': '功盖', 'meaning': '功业卓著、超越他人；诗中称颂诸葛亮。'},
            {'term': '三分国', 'meaning': '魏、蜀、吴三国鼎立的局面。'},
            {'term': '八阵图', 'meaning': '诸葛亮所创阵法，诗中兼指其布阵遗迹。'},
            {'term': '石不转', 'meaning': '任凭江水冲流，布阵的石头仍然不移动。'},
            {'term': '失吞吴', 'meaning': '这里按通行解释译作刘备伐吴失策；另有未能吞吴、八阵图未尽其用等解释，末句古义存在争论。'},
        ]},
    'tang-104': {'notes': [
        {'term': '登高', 'meaning': '重阳节登高望远的习俗。'},
        {'term': '举觞', 'meaning': '举杯饮酒，觞是酒杯。'},
        {'term': '两重阳', 'meaning': '把九月九日重阳和次日继续登高饮酒相提并论，写菊花接连被采折的苦处，并非两个不同的正式重阳节。'},
    ]},
    'tang-119': {
        'translation': '一树寒梅，花满枝头，洁白得如同玉条；远远地立在村路旁、溪桥边。人们不知道它靠近水边、花开得早，还以为那是经过冬天尚未融化的积雪。',
        'notes': [
            {'term': '白玉条', 'meaning': '以白玉般的枝条形容梅花满枝的洁白景象。'},
            {'term': '迥', 'meaning': '远，写梅树远远临着村路。'},
            {'term': '傍', 'meaning': '靠近、旁边。'},
            {'term': '发', 'meaning': '花开放。'},
            {'term': '销', 'meaning': '同“消”，这里指冰雪融化。'},
        ]},
    'tang-121': {
        'translation': '青山隐隐，江水迢迢；深秋的江南，草木还没有凋零。在扬州二十四桥明月照耀的夜晚，风流俊雅的你，又在哪里教人吹箫呢？',
        'notes': [
            {'term': '隐隐', 'meaning': '若隐若现的样子。'},
            {'term': '迢迢', 'meaning': '绵长遥远的样子。'},
            {'term': '二十四桥', 'meaning': '联系扬州桥梁名胜，具体所指有诸桥总称与桥名等说法。'},
            {'term': '玉人', 'meaning': '通行解释为对韩绰风流俊雅的戏称，也有指美人的解释；译文取前说。'},
            {'term': '教', 'meaning': '教导；在诗中构成对友人生活的想象和打趣。'},
        ]},
    'tang-131': {
        'translation': '细雨中，一两户人家传来鸡鸣；竹溪旁的村路上，木板桥斜斜地架着。婆媳相互招呼着，忙着去浸洗蚕种；院中的栀子花开着，显得分外清闲。',
        'notes': [
            {'term': '一两家', 'meaning': '写传来鸡声的人家稀疏，不等于断言全村总共只有一两户。'},
            {'term': '妇姑', 'meaning': '媳妇和婆婆。'},
            {'term': '浴蚕', 'meaning': '旧时养蚕的浸洗蚕种习俗。'},
            {'term': '闲看', 'meaning': '此句常以栀子花的闲静衬托农家的忙碌；句法和观看者所指有不同理解，译文保留忙与闲的对照。'},
            {'term': '中庭', 'meaning': '庭院中。'},
        ]},
}

SOURCES = [
    {'url': 'https://idl.hbdlib.cn/book/00000000000000/pdfbook/009/003/106702.pdf',
     'usage': '八阵图通行解释对照；译文独立改写。'},
    {'url': 'https://ny.zdline.cn/h5/article/detail.do?artId=62260',
     'usage': '孙玉文对失吞吴不同理解的讨论，保留争议。'},
    {'url': 'https://www.quanxue.cn/ct_rujia/qianjias/qianjias57.html',
     'usage': '山亭夏日水晶帘的池面比喻解释对照。'},
]


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    pipe = Pipeline()
    _, drafts, _, _ = pipe.inspect()
    approved = []
    # 118 has a possible source variant, kept pending rather than silently changed.
    for number in range(82, 132):
        pid = f'tang-{number:03}'
        if pid == 'tang-118':
            continue
        record = drafts[pid]
        patch = copy.deepcopy(record['patch'])
        patch.update(EDITS.get(pid, {}))
        path = pipe.result_path(pipe.poems[pid])
        if path.exists() and read(path) != patch:
            archive = pipe.work / 'history' / (pid + '--' + digest(read(path)) + '.json')
            write_once(archive, read(path))
            path.write_text(json.dumps(patch, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        else:
            write_once(path, patch)
        validate_patch(patch, pipe.poems[pid], pipe.tags[pipe.poems[pid]['category']])
        review = dict(decision='approved', reviewer='Codex editorial review 2026-11-04',
                      inputHash=record['inputHash'], resultHash=digest(patch),
                      scope='逐篇对照正文检查译文覆盖、主体时态和注释；不宣称已完成来源版本逐字校勘。',
                      edited=pid in EDITS)
        write_once(pipe.work/'reviews'/(pid+'--'+record['inputHash']+'.json'), review)
        approved.append(pid)
    write_once(pipe.work/'reviews'/'tang-082-131-review-log.json',
               dict(ids=approved, sources=SOURCES, excluded=[dict(id='tang-118',
                    reason='原文动地京与常见帝京有版本疑点，现稿把地京解成词语；先保留待核。')]))
    print(f'Editorial review saved: {len(approved)} poems; tang-118 remains pending.')


if __name__ == '__main__':
    main()
