// Native dialogs provide focus containment, Escape support and inert background.
document.documentElement.classList.add('js');
const drawer = document.querySelector('#mobile-nav');
const menuButton = document.querySelector('#menu-open');
if (drawer && menuButton) {
    menuButton.addEventListener('click', () => {
        drawer.showModal();
        menuButton.setAttribute('aria-expanded', 'true');
    });
    const closeMenu = () => drawer.close();
    drawer.querySelector('[data-close-menu]').addEventListener('click', closeMenu);
    drawer.querySelectorAll('a').forEach(link => link.addEventListener('click', closeMenu));
    drawer.addEventListener('click', event => {
        if (event.target === drawer && event.clientX < drawer.getBoundingClientRect().left)
            closeMenu();
    });
    drawer.addEventListener('close', () => {
        menuButton.setAttribute('aria-expanded', 'false');
        menuButton.focus({
            preventScroll: true
        });
    });
}
const lightbox = document.querySelector('#lightbox');
const photos = [...document.querySelectorAll('[data-lightbox]')];
if (lightbox && photos.length) {
    let index = 0,
        origin = null,
        touchX = 0;
    const image = lightbox.querySelector('#lightbox-image');
    const show = next => {
        index = (next + photos.length) % photos.length;
        image.src = photos[index].href;
        image.alt = photos[index].dataset.alt || '';
        lightbox.querySelector('#lightbox-caption').textContent = photos[index].dataset
            .caption || '';
        lightbox.querySelector('#lightbox-counter').textContent =
            `${index + 1} / ${photos.length}`;
    };
    photos.forEach((photo, i) => photo.addEventListener('click', event => {
        event.preventDefault();
        origin = photo;
        show(i);
        lightbox.showModal();
    }));
    lightbox.querySelector('[data-close]').addEventListener('click', () => lightbox.close());
    lightbox.querySelector('[data-prev]').addEventListener('click', () => show(index - 1));
    lightbox.querySelector('[data-next]').addEventListener('click', () => show(index + 1));
    lightbox.addEventListener('keydown', event => {
        if (event.key === 'ArrowLeft') {
            event.preventDefault();
            show(index - 1);
        }
        if (event.key === 'ArrowRight') {
            event.preventDefault();
            show(index + 1);
        }
    });
    lightbox.addEventListener('touchstart', event => {
        touchX = event.changedTouches[0].screenX;
    }, {
        passive: true
    });
    lightbox.addEventListener('touchend', event => {
        const delta = event.changedTouches[0].screenX - touchX;
        if (Math.abs(delta) > 60) show(index + (delta < 0 ? 1 : -1));
    }, {
        passive: true
    });
    lightbox.addEventListener('close', () => origin?.focus());
}
const inquiryForm = document.querySelector('.inquiry-form');
if (inquiryForm) {
    const submit = inquiryForm.querySelector('[type=submit]');
    const label = submit.value;
    inquiryForm.addEventListener('submit', () => {
        submit.disabled = true;
        submit.value = 'Mengirim…';
    });
    window.addEventListener('pageshow', () => {
        submit.disabled = false;
        submit.value = label;
    });
}
