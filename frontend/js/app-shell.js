/* Keeps the authenticated navigation identical on every product page. */
document.addEventListener('DOMContentLoaded', () => {
  const sidebar = document.querySelector('.sidebar');
  if (!sidebar) return;

  const currentPage = window.location.pathname.split('/').pop() || 'dashboard';
  const workspace = [
    ['dashboard', 'speedometer2', 'Dashboard'],
    ['jobs', 'folder2-open', 'Jobs'],
    ['uploads', 'cloud-upload', 'Uploads'],
    ['mapping', 'columns-gap', 'Column mapping'],
    ['reconciliation', 'arrow-left-right', 'Reconcile'],
    ['results', 'table', 'Results']
  ];
  const administration = [
    ['manage_staff', 'people', 'Team'],
    ['subscription', 'credit-card', 'Subscription'],
    ['settings', 'gear', 'Settings']
  ];
  const navItem = ([href, icon, label]) => `<a href="${href}"${href === currentPage ? ' class="active" aria-current="page"' : ''}><i class="bi bi-${icon}" aria-hidden="true"></i>${label}</a>`;

  sidebar.innerHTML = `
    <a class="logo" href="/dashboard" aria-label="Recon dashboard">Recon</a>
    <nav aria-label="Workspace">${workspace.map(navItem).join('')}</nav>
    <nav class="sidebar-admin" aria-label="Administration">${administration.map(navItem).join('')}</nav>
    <div class="sidebar-bottom"><button type="button" class="logout-btn" onclick="logout()"><i class="bi bi-box-arrow-right" aria-hidden="true"></i> Sign out</button></div>`;
});
