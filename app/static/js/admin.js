const selection = document.querySelector('#media_ids');
const orderInput = document.querySelector('#media_order');
const orderList = document.querySelector('#gallery-order');
if (selection && orderInput && orderList) {
    let order = orderInput.value.split(',').filter(Boolean);
    const render = () => {
        const selected = [...selection.selectedOptions].map(option => option.value);
        order = [...new Set([...order.filter(id => selected.includes(id)), ...selected])];
        orderInput.value = order.join(',');
        orderList.replaceChildren();
        order.forEach((id, index) => {
            const li = document.createElement('li'),
                label = document.createElement('span');
            label.textContent = [...selection.options].find(option => option.value ===
                id)?.textContent || id;
            li.append(label);
            [
                ['Naik', -1],
                ['Turun', 1]
            ].forEach(([text, offset]) => {
                const button = document.createElement('button');
                button.type = 'button';
                button.textContent = text;
                button.setAttribute('aria-label',
                    `${text}: ${label.textContent}`);
                button.disabled = index + offset < 0 || index + offset >= order
                    .length;
                button.addEventListener('click', () => {
                    [order[index], order[index + offset]] = [order[
                        index + offset], order[index]];
                    render();
                    orderList.children[index + offset]?.querySelector(
                        'button')?.focus();
                });
                li.append(button);
            });
            orderList.append(li);
        });
    };
    selection.addEventListener('change', render);
    render();
}
const upload = document.querySelector('#upload-form');
if (upload && window.fetch && window.FormData) {
    const input = upload.querySelector('input[type=file]');
    input.multiple = true;
    input.accept = '.jpg,.jpeg,.png,.webp';
    upload.addEventListener('submit', async event => {
        if (!input.files.length) return;
        event.preventDefault();
        const submit = upload.querySelector('[type=submit]'),
            results = document.querySelector('#upload-results');
        const files = [...input.files];
        results.replaceChildren();
        submit.disabled = true;
        let failed = false;
        for (const file of files) {
            const item = document.createElement('li');
            item.textContent = `${file.name}: sedang diproses…`;
            results.append(item);
            const data = new FormData(upload);
            data.set('image', file);
            try {
                const response = await fetch(upload.action || location.href, {
                    method: 'POST',
                    body: data,
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest'
                    }
                });
                const result = await response.json();
                if (!response.ok || !result.ok) throw new Error(Object.values(result
                        .errors || {}).flat().join(' ') ||
                    'Unggahan ditolak. Muat ulang halaman jika sesi form berakhir.'
                );
                item.textContent = `${file.name}: berhasil diunggah.`;
                item.className = 'upload-result-success';
            } catch (error) {
                item.textContent = `${file.name}: ${error.message}`;
                item.className = 'upload-result-error';
                failed = true;
            }
        }
        submit.disabled = false;
        if (!failed) input.value = '';
    });
}
