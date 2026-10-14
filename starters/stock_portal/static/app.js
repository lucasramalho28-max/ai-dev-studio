'use strict';
const fillDemo = document.getElementById('fill-demo');
if (fillDemo) fillDemo.addEventListener('click', () => {
  document.getElementById('username').value = fillDemo.dataset.username;
  document.getElementById('password').value = fillDemo.dataset.password;
  document.getElementById('username').focus();
});
