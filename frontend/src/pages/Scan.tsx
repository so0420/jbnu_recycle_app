import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Icon } from '../components/Art';
import PhotoPicker from '../components/PhotoPicker';
import { PageHead } from '../components/common';
import { send, upload } from '../lib/api';
import { shrinkPhoto } from '../lib/device';
import { TYPE_NAMES } from '../lib/labels';
import { errMsg, useStore } from '../lib/store';
import type { Guide } from '../lib/types';

interface ScanRes {
  log_id: number;
  result: { category: string | null; clean: boolean | null; habit_ok: boolean | null; judged_by: string; confidence: number; latency_ms: number };
  guide: Guide | null;
  candidates: Guide[];
  reward: {
    xp: number;
    bag: null | { added: boolean; count: number; capacity: number };
    habit: null | { type: string; count: number };
    dex_new: string | null;
    duplicate: boolean;
  };
}

const TYPE_ICON: Record<string, string> = { plastic: 'mat_plastic', paper: 'mat_paper', metal: 'mat_metal', glass: 'mat_glass', vinyl: 'mat_vinyl', volt: 'mat_volt', fabric: 'mat_fabric' };

export function GuideCard({ g }: { g: Guide }) {
  return (
    <div className="card pop">
      <div className="result-head">
        {g.recyclable ? <Icon name={TYPE_ICON[g.type] ?? 'bag'} size={64} /> : <Icon name="bag" size={64} />}
        <div className="col" style={{ gap: 2 }}>
          <span className={`chip ${g.recyclable ? g.type : 'none'}`}>{g.recyclable ? `${TYPE_NAMES[g.type]} · ${g.category_name}` : '재활용 안 돼요'}</span>
          <h2>{g.item?.name ?? g.category_name}</h2>
        </div>
      </div>
      {g.item ? <p className="method">{g.item.method}</p> : <p className="method">{g.category_name}(으)로 배출해요</p>}
      {g.item?.caution && <p className="caution">⚠ {g.item.caution}</p>}
    </div>
  );
}

export default function Scan() {
  const { refresh, toast } = useStore();
  const [preview, setPreview] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [res, setRes] = useState<ScanRes | null>(null);
  const [chosen, setChosen] = useState<Guide | null>(null);

  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview); }, [preview]);

  async function onPick(file: File) {
    setRes(null);
    setChosen(null);
    setBusy(true);
    try {
      const blob = await shrinkPhoto(file);
      setPreview(URL.createObjectURL(blob));
      const fd = new FormData();
      fd.append('photo', blob, 'scan.jpg');
      const r = await upload<ScanRes>('/scan', fd);
      setRes(r);
      void refresh();
    } catch (e) {
      toast(errMsg(e), 'err');
    } finally {
      setBusy(false);
    }
  }

  async function choose(c: Guide) {
    if (!res) return;
    try {
      const r = await send<{ guide: Guide }>(`/scan/${res.log_id}/choose`, 'POST', { category: c.category });
      setChosen(r.guide);
    } catch (e) {
      toast(errMsg(e), 'err');
    }
  }

  const g = res?.guide ?? chosen;
  return (
    <>
      <PageHead title="쓰레기 스캔" back={false} right={<Link className="btn ghost sm" to="/bag">가방</Link>} />
      {!busy && !res && (
        <PhotoPicker onPick={onPick} title="버릴 물건을 찍어 주세요" hint="한 번에 하나씩, 물건이 크게 나오게 찍으면 정확해요. 버리는 법을 알려 주고 가방에 담아 둘게요." />
      )}
      {preview && <img className="shot" src={preview} alt="찍은 사진" />}
      {busy && (
        <div className="card center">
          <div className="spinner" />
          <p className="muted small">AI가 보고 있어요… (5~10초)</p>
        </div>
      )}
      {res && !g && (
        <div className="card">
          <h3>무엇인지 잘 모르겠어요</h3>
          {res.candidates.length > 0 ? (
            <>
              <p className="small muted">아래에서 골라 주시면 버리는 법을 알려 드릴게요.</p>
              <div className="col">
                {res.candidates.filter(Boolean).map((c) => (
                  <button key={c.category} className="btn ghost block" onClick={() => choose(c)}>{c.category_name}</button>
                ))}
              </div>
            </>
          ) : (
            <p className="small muted">사진을 다시 찍어 주세요. 밝은 곳에서 물건 하나만 크게 찍으면 좋아요.</p>
          )}
        </div>
      )}
      {g && <GuideCard g={g} />}
      {res?.guide && (
        <div className="card">
          <h3>보상</h3>
          <div className="reward-list">
            {res.reward.duplicate && <div className="r">같은 사진은 보상이 없어요</div>}
            {res.reward.xp > 0 && <div className="r"><Icon name="coin" size={22} />정원 경험치 +{res.reward.xp}</div>}
            {res.reward.bag?.added && <div className="r"><Icon name="bag" size={22} />가방에 담았어요 ({res.reward.bag.count}/{res.reward.bag.capacity}) · 배출 인증 때 재료로 바뀌어요</div>}
            {res.reward.bag && !res.reward.bag.added && <div className="r"><Icon name="bag" size={22} />가방이 가득 찼어요. 배출 인증으로 비워 주세요</div>}
            {res.result.clean === false && <div className="r">⚠ 오염된 것 같아요. 헹구면 깨끗한 보너스를 받아요</div>}
            {res.reward.habit && <div className="r"><Icon name="stamp" size={22} />올바른 습관 +1 ({TYPE_NAMES[res.reward.habit.type]} {res.reward.habit.count}회) · 진화에 필요해요</div>}
            {res.result.habit_ok === false && res.guide.habit_name && <div className="r small">다음엔 '{res.guide.habit_name}'로 찍어 보세요. 진화 조건이에요</div>}
            {res.reward.dex_new && <div className="r"><Icon name="stamp" size={22} />품목 도감에 새로 기록했어요</div>}
          </div>
          <p className="tiny muted">판정: {res.result.judged_by === 'openai' ? 'AI' : '사용자 선택'} · {(res.result.latency_ms / 1000).toFixed(1)}초</p>
        </div>
      )}
      {(res || chosen) && !busy && (
        <PhotoPicker onPick={onPick} title="하나 더 찍기" hint="" />
      )}
    </>
  );
}
