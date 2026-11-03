# Modified for MahjongCopilotPlus on 2026-11-03; see NOTICE.md.
"""Game-native HTML card, using CSS layout for aligned text and probabilities."""

RENDER_GUIDE = r"""({id, line, options, left, top, width, height, rows}) => {
    let card = document.getElementById(id);
    if (!card) {
        card = document.createElement('div');
        card.id = id;
        card.setAttribute('aria-label', 'AI');
        document.body.appendChild(card);
    }
    const font = Math.max(12, Math.min(20, height / 54));
    Object.assign(card.style, {
        position: 'fixed', left: `${left + width * 0.14}px`,
        top: `${top + height * 0.44}px`, boxSizing: 'border-box',
        width: `${Math.min(font * 13.4, width - 16)}px`,
        padding: `${font * 0.45}px ${font * 0.65}px`,
        border: '1px solid rgba(225,235,250,0.12)', borderRadius: `${font * 0.5}px`,
        background: 'rgba(29,32,38,0.94)',
        backdropFilter: 'blur(8px)', boxShadow: '0 6px 22px rgba(0,0,0,0.22)',
        color: '#e4eaf2', fontFamily: '"Microsoft YaHei", "Segoe UI", "Segoe UI Emoji", sans-serif',
        fontSize: `${font}px`, lineHeight: '1.25', pointerEvents: 'auto',
        cursor: 'grab', touchAction: 'none',
        zIndex: '9999999', userSelect: 'none'
    });
    // The card itself is the drag surface: no grip, header, or extra empty row.
    // Pointer capture stays on the card while advice rows are replaced.
    if (!card._guide) {
        const grip = card;
        grip.dataset.guideDrag = '';
        grip.title = '拖动移动；右键或双击恢复默认位置';
        grip.setAttribute('aria-label', '拖动 AI 提示框');
        const content = document.createElement('div');
        card.append(content);
        const storageKey = 'copilot.guide.position.v1';
        const state = card._guide = {grip, content, drag: null};
        const valid = p => p && Number.isFinite(p.x) && Number.isFinite(p.y)
            && p.x >= 0 && p.x <= 1 && p.y >= 0 && p.y <= 1;
        if (window._copilotGuidePosition === undefined) {
            window._copilotGuidePosition = null;
            try {
                const saved = JSON.parse(localStorage.getItem(storageKey));
                if (valid(saved)) window._copilotGuidePosition = saved;
            } catch (_) { /* Storage may be disabled; dragging still works. */ }
        }
        state.place = () => {
            const g = state.geometry;
            const bounds = card.getBoundingClientRect();
            const minX = Math.max(0, g.left), minY = Math.max(0, g.top);
            const spanX = Math.max(0, Math.min(innerWidth, g.left + g.width) - minX - bounds.width);
            const spanY = Math.max(0, Math.min(innerHeight, g.top + g.height) - minY - bounds.height);
            state.bounds = {minX, minY, spanX, spanY};
            const p = window._copilotGuidePosition;
            card.style.left = `${minX + (p ? spanX * p.x : Math.min(spanX, g.width * 0.14))}px`;
            card.style.top = `${minY + (p ? spanY * p.y : Math.min(spanY, g.height * 0.44))}px`;
        };
        const persist = () => {
            try {
                if (window._copilotGuidePosition) {
                    localStorage.setItem(storageKey, JSON.stringify(window._copilotGuidePosition));
                } else localStorage.removeItem(storageKey);
            } catch (_) { /* Retain the in-page position without storage. */ }
        };
        const finish = event => {
            if (!state.drag || event.pointerId !== state.drag.id) return;
            state.drag = null;
            grip.style.cursor = 'grab';
            if (grip.hasPointerCapture(event.pointerId)) grip.releasePointerCapture(event.pointerId);
            persist();
            event.stopPropagation();
        };
        grip.addEventListener('pointerdown', event => {
            if (event.button !== 0) return;
            const rect = card.getBoundingClientRect();
            state.drag = {id: event.pointerId, dx: event.clientX - rect.left, dy: event.clientY - rect.top};
            grip.setPointerCapture(event.pointerId);
            grip.style.cursor = 'grabbing';
            event.preventDefault();
            event.stopPropagation();
        });
        grip.addEventListener('pointermove', event => {
            if (!state.drag || event.pointerId !== state.drag.id) return;
            const b = state.bounds;
            const x = Math.max(0, Math.min(b.spanX, event.clientX - state.drag.dx - b.minX));
            const y = Math.max(0, Math.min(b.spanY, event.clientY - state.drag.dy - b.minY));
            window._copilotGuidePosition = {x: b.spanX ? x / b.spanX : 0, y: b.spanY ? y / b.spanY : 0};
            state.place();
            event.stopPropagation();
        });
        grip.addEventListener('pointerup', finish);
        grip.addEventListener('pointercancel', finish);
        grip.addEventListener('lostpointercapture', finish);
        grip.addEventListener('click', event => event.stopPropagation());
        const reset = event => {
            window._copilotGuidePosition = null;
            persist();
            state.place();
            event.stopPropagation();
            event.preventDefault();
        };
        grip.addEventListener('dblclick', reset);
        grip.addEventListener('contextmenu', reset);
    }
    const state = card._guide;
    state.geometry = {left, top, width, height};
    state.content.replaceChildren();

    // Show the chosen action's probability only when its label matches.
    // This also works when randomized play chooses something below rank one.
    const matching = options.map((item, index) => line.endsWith(item[0]) ? index : -1)
                            .filter(index => index >= 0);
    const selected = matching.length === 1 ? matching[0] : -1;
    const makeRow = (label, weight, primary, tokens) => {
        const row = document.createElement('div');
        row.dataset.guideRow = primary ? 'primary' : 'alternative';
        Object.assign(row.style, {
            display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) auto',
            columnGap: `${font * 0.65}px`, alignItems: 'center',
            padding: primary ? '0' : `${font * 0.12}px 0`
        });
        const text = document.createElement('span');
        text.dataset.guideLabel = '';
        text.setAttribute('aria-label',label);
        if (tokens) {
            Object.assign(text.style,{display:'flex',alignItems:'center',flexWrap:'wrap',gap:`${font*.25}px`});
            tokens.forEach(token => {
                const element = document.createElement('span');
                if (token.tile) {
                    const tile = token.tile;
                    element.dataset.guideTile = tile.code;
                    const height = font*(primary?2.4:2.05);
                    Object.assign(element.style,{position:'relative',display:'inline-flex',flexDirection:'column',
                        alignItems:'center',justifyContent:'center',flexShrink:'0',
                        width:`${height*.75}px`,height:`${height}px`,borderRadius:'4px',
                        background:'#e1dfd8',color:tile.color,boxShadow:'inset 0 -2px #b4b0a5',
                        fontSize:`${height*.49}px`,fontWeight:'500',lineHeight:'1'});
                    element.textContent = tile.value;
                    if(tile.suit) {
                        const suit = document.createElement('small');
                        suit.textContent=tile.suit;
                        Object.assign(suit.style,{fontSize:`${height*.27}px`,marginTop:'2px',lineHeight:'1'});
                        element.append(suit);
                    }
                    if(tile.red) {
                        const red = document.createElement('span');
                        Object.assign(red.style,{position:'absolute',top:'3px',right:'3px',width:'3px',height:'3px',borderRadius:'50%',background:'#c84d52'});
                        element.append(red);
                    }
                } else element.textContent = token.text || '';
                text.append(element);
            });
        } else text.textContent = label;
        Object.assign(text.style, {minWidth: '0', overflowWrap: 'anywhere',
            fontSize: `${font * (primary ? 1.18 : 0.94)}px`,
            fontWeight: primary ? '500' : '400', color: primary ? '#eef0f3' : '#c7ccd3'});
        const probability = document.createElement('span');
        probability.dataset.guideProbability = '';
        probability.textContent = weight == null ? '' : `${Math.round(weight * 100)}%`;
        Object.assign(probability.style, {textAlign: 'right', whiteSpace: 'nowrap',
            fontVariantNumeric: 'tabular-nums', fontFamily: '"Segoe UI", sans-serif',
            fontSize: `${font * (primary ? 1.05 : 0.94)}px`,
            fontWeight: primary ? '500' : '400', color: primary ? '#eef0f3' : '#959ba5'});
        row.append(text, probability);
        state.content.appendChild(row);
    };
    const displayRows = rows || [{label:line,weight:selected<0?null:options[selected][1],primary:true},
        ...options.filter((_,index)=>index!==selected).map(([label,weight])=>({label,weight,primary:false}))];
    displayRows.forEach((row,index) => {
      if (index === 1) {
        const divider = document.createElement('div');
        Object.assign(divider.style, {height: '1px', margin: `${font * 0.3}px 0`,
            background: 'rgba(225,235,250,0.12)'});
        state.content.appendChild(divider);
      }
      makeRow(row.label,row.weight,row.primary,row.tokens);
    });
    state.place();
}"""
