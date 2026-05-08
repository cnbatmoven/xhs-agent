// Mock data + JSON/Markdown samples
export const MOCK_NOTES = [
  { id: '67f2a1b3', title: '上海City Walk｜武康路下午茶宝藏小店', author: '小薯条吃遍上海', avatar: 'S', likes: 12483, collects: 3201, comments: 287, shares: 156, time: '2026-04-22', tags: ['citywalk', '武康路', '下午茶'], cover: '#ffd4a3' },
  { id: '67f2a1b4', title: '换季护肤｜油皮闭口救星实测30天', author: '皮肤管理日记', avatar: 'P', likes: 8932, collects: 5612, comments: 412, shares: 89, time: '2026-04-21', tags: ['护肤', '油皮', '闭口'], cover: '#ffb8c1' },
  { id: '67f2a1b5', title: '通勤穿搭｜新中式上衣怎么搭不土', author: 'Yuki的衣橱', avatar: 'Y', likes: 23104, collects: 8923, comments: 1023, shares: 432, time: '2026-04-20', tags: ['穿搭', '新中式'], cover: '#c8a8ff' },
  { id: '67f2a1b6', title: '考研经验｜双非上岸211全过程', author: '阿玲学姐', avatar: 'A', likes: 5621, collects: 4892, comments: 234, shares: 178, time: '2026-04-20', tags: ['考研', '经验贴'], cover: '#a8d8ff' },
  { id: '67f2a1b7', title: '露营装备清单｜新手向第一次露营', author: '山野记', avatar: 'M', likes: 9821, collects: 6234, comments: 156, shares: 234, time: '2026-04-19', tags: ['露营', '装备', '新手'], cover: '#a8ffc8' },
  { id: '67f2a1b8', title: '减脂餐谱｜30天瘦8斤不饿肚子', author: '健身的鱼', avatar: 'F', likes: 17234, collects: 12034, comments: 689, shares: 543, time: '2026-04-18', tags: ['减脂', '食谱'], cover: '#ffe0a8' },
];

export const MOCK_GRID = Array.from({ length: 24 }, (_, i) => {
  const palette = ['#ffd4a3', '#ffb8c1', '#c8a8ff', '#a8d8ff', '#a8ffc8', '#ffe0a8', '#ffc8e0', '#d4a8ff'];
  return {
    id: 'g' + i,
    color: palette[i % palette.length],
    likes: Math.floor(2000 + ((i * 1373) % 18000)),
    title: ['武康路打卡', '新中式穿搭', '减脂晚餐', '油皮护肤', '露营清单', '考研日记'][i % 6],
  };
});

export const MOCK_CHART = [12, 28, 19, 45, 38, 62, 51];

export const JSON_SAMPLE = `{
  "id": "67f2a1b3",
  "title": "上海City Walk｜武康路下午茶宝藏小店",
  "author": {
    "id": "u_8821",
    "name": "小薯条吃遍上海",
    "followers": 23401
  },
  "stats": {
    "likes": 12483,
    "collects": 3201,
    "comments": 287,
    "shares": 156
  },
  "tags": ["citywalk", "武康路", "下午茶"],
  "publishedAt": "2026-04-22T14:30:00+08:00"
}`;

export function fmt(n) {
  if (n >= 10000) return (n / 10000).toFixed(1) + '万';
  if (n >= 1000) return (n / 1000).toFixed(1) + 'k';
  return String(n);
}
