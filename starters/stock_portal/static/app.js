'use strict';
const fillDemo = document.getElementById('fill-demo');
if (fillDemo) fillDemo.addEventListener('click', () => {
  document.getElementById('username').value = fillDemo.dataset.username;
  document.getElementById('password').value = fillDemo.dataset.password;
  document.getElementById('username').focus();
});

// Keep section navigation aligned with clicks, deep links and manual scrolling.
const sectionLinks = [...document.querySelectorAll('.sidebar nav a[data-section]')];
if (sectionLinks.length) {
  const sections = sectionLinks.map(link => document.getElementById(link.dataset.section));
  function selectSection(id) {
    sectionLinks.forEach(link => {
      const selected = link.dataset.section === id;
      link.classList.toggle('selected', selected);
      if (selected) link.setAttribute('aria-current', 'location');
      else link.removeAttribute('aria-current');
    });
  }
  function selectFromScroll() {
    let current = 'overview';
    sections.forEach(section => {
      if (section && section.getBoundingClientRect().top <= 150) current = section.id;
    });
    const last = sections[sections.length - 1];
    if (last && window.scrollY > 0 && window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 2) current = last.id;
    selectSection(current);
  }
  sectionLinks.forEach(link => link.addEventListener('click', () => selectSection(link.dataset.section)));
  window.addEventListener('hashchange', () => {
    const id = location.hash.slice(1);
    if (sections.some(section => section && section.id === id)) selectSection(id);
    else selectFromScroll();
  });
  let scheduled = false;
  window.addEventListener('scroll', () => {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(() => { scheduled = false; selectFromScroll(); });
  }, {passive:true});
  window.addEventListener('resize', selectFromScroll);
  const initial = location.hash.slice(1);
  if (sections.some(section => section && section.id === initial)) selectSection(initial);
  else selectFromScroll();
}
