// Email accounts: signup, login, the signed-in dashboard, and the admin user list.
import { get, post } from '../api.js';
import { html, raw, icons, toast, timeAgo, modal } from '../ui.js';
import { state, prefs, profileInitials, setProfile, setAccount } from '../store.js';
import { navigate, onViewCleanup } from '../router.js';
import { sectionHead } from '../components.js';

function dateLabel(value) {
  if (!value) return '—';
  try {
    return new Date(value).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
  } catch { return value; }
}

export async function accountView(root, ctx) {
  const account = state.account;
  const age = Number(state.profile?.survey?.age || 13);
  document.body.classList.toggle('auth-mode', !account);
  onViewCleanup(() => document.body.classList.remove('auth-mode'));
  root.innerHTML = account ? dashboard(account) : authPage(age);
  if (account) {
    bindDashboard(root, account);
    if (account.is_admin) loadUsers(root);
  } else {
    bindAuth(root, ctx);
  }
}

function authPage(age = 13) {
  const canCreate = age >= 13;
  return html`
    <div class="auth-page">
      <aside class="auth-page__aside">
        <a class="brand auth-page__brand" href="/" data-link aria-label="Pulse home">
          <span class="brand__pulse" aria-hidden="true"><span></span><span></span><span></span><span></span></span>
          <img class="brand__season" data-season-icon alt="" hidden>
          <span class="brand__name">Pulse</span>
        </a>
        <div class="auth-page__copy">
          <p class="eyebrow">Pulse account</p>
          <h1>Your reading,<br><em>in sync.</em></h1>
          <p class="page-sub">Keep your history, saves, streak and preferences across every browser that can reach this Pulse server.</p>
        </div>
        <div class="auth-art" aria-hidden="true">
          <div class="auth-art__bar"><span>Reading profile</span><span class="live-dot"></span></div>
          <div class="auth-art__signal">${raw(icons.signal)}</div>
          <div class="auth-art__rows">
            <div><span>Archive</span><b>searchable</b></div>
            <div><span>Progress</span><b>synced</b></div>
            <div><span>Data</span><b>on your server</b></div>
          </div>
        </div>
        <p class="auth-page__fine">No ads. No tracking. No third-party analytics.</p>
      </aside>

      <main class="auth-page__main">
        <div class="account__grid">
          ${canCreate ? html`<form class="card card-pad-lg account__form" data-signup-form>
            <div class="account__form-head">
              <span class="account__icon">${raw(icons.user)}</span>
              <div><h2>Create an account</h2><p class="tiny muted">The first account becomes the admin.</p></div>
            </div>
            <label class="account__label" for="signup-name">Name</label>
            <input id="signup-name" name="name" type="text" autocomplete="name" maxlength="40" placeholder="First name or nickname" value="${state.profile?.name || ''}">
            <label class="account__label" for="signup-email">Email</label>
            <input id="signup-email" name="email" type="email" autocomplete="email" maxlength="254" placeholder="you@example.com" required>
            <label class="account__label" for="signup-password">Password</label>
            <input id="signup-password" name="password" type="password" autocomplete="new-password" minlength="8" placeholder="At least 8 characters" required>
            <button class="btn btn--primary btn--block" type="submit">Create account ${raw(icons.chevron)}</button>
            <p class="account__fine">Stored on this server only. This build has no mail server, so pick a password you’ll remember.</p>
          </form>` : html`
          <div class="card card-pad-lg account__form">
            <div class="account__form-head">
              <span class="account__icon">13+</span>
              <div><h2>Accounts are for 13+</h2><p class="tiny muted">Younger readers keep using Pulse as a guest on this device.</p></div>
            </div>
            <p class="small muted">Guest mode still keeps your streak, saves and reading history on this device. Email accounts are limited to ages 13 and up for privacy reasons.</p>
            <a class="btn btn--sm btn--ghost" href="/privacy" data-link>Read the privacy note</a>
          </div>`}

          <form class="card card-pad-lg account__form" data-login-form>
            <div class="account__form-head">
              <span class="account__icon">${raw(icons.user)}</span>
              <div><h2>Sign in</h2><p class="tiny muted">Welcome back — your streak is waiting.</p></div>
            </div>
            <label class="account__label" for="login-email">Email</label>
            <input id="login-email" name="email" type="email" autocomplete="email" maxlength="254" placeholder="you@example.com" required>
            <label class="account__label" for="login-password">Password</label>
            <input id="login-password" name="password" type="password" autocomplete="current-password" placeholder="Your password" required>
            <button class="btn btn--primary btn--block" type="submit">Sign in</button>
            <p class="account__fine">One account works on any browser that can reach this server.</p>
          </form>
        </div>
        <p class="auth-page__legal"><a href="/privacy" data-link>Privacy</a> · <a href="/terms" data-link>Terms</a></p>
      </main>
    </div>`;
}

function bindAuth(root, ctx) {
  const signup = root.querySelector('[data-signup-form]');
  const login = root.querySelector('[data-login-form]');

  signup?.addEventListener('submit', async (event) => {
    event.preventDefault();
    const button = signup.querySelector('button');
    button.disabled = true;
    try {
      const result = await post('/api/auth/signup', {
        name: signup.querySelector('#signup-name').value.trim(),
        email: signup.querySelector('#signup-email').value.trim(),
        password: signup.querySelector('#signup-password').value,
      });
      setProfile(result.profile);
      setAccount(result.account);
      toast(result.account.is_admin ? 'Account created — you are the admin' : 'Account created', { type: 'good' });
      navigate(result.profile.onboarded ? '/' : '/onboarding', { replace: true });
    } catch (err) {
      toast(err.message || 'Could not create the account.', { type: 'bad' });
      button.disabled = false;
    }
  });

  login.addEventListener('submit', async (event) => {
    event.preventDefault();
    const button = login.querySelector('button');
    button.disabled = true;
    try {
      const result = await post('/api/auth/login', {
        email: login.querySelector('#login-email').value.trim(),
        password: login.querySelector('#login-password').value,
      });
      setProfile(result.profile);
      setAccount(result.account);
      toast('Signed in');
      navigate(result.profile.onboarded ? '/' : '/onboarding', { replace: true });
    } catch (err) {
      toast(err.message || 'Could not sign in.', { type: 'bad' });
      button.disabled = false;
    }
  });
  void ctx;
}

function dashboard(account) {
  const displayName = state.profile?.name || account.name || 'Your account';
  const photo = prefs().avatar || '';
  return html`
    <div class="account">
      <div class="account__hero">
        <p class="eyebrow">Pulse account</p>
        <h1>${displayName}</h1>
        <p class="page-sub">${account.is_admin ? 'You are the admin for this Pulse server.' : 'Your reading history is attached to this account.'}</p>
      </div>

      <div class="account__grid">
        <div class="card card-pad-lg">
          <div class="account__form-head">
            <span class="account__avatar ${photo ? 'account__avatar--photo' : ''}" ${photo ? html`style="background-image:url('${photo}')"` : ''}>${photo ? '' : profileInitials()}</span>
            <div><h2>${displayName}</h2><p class="tiny muted">${account.email} · ${account.is_admin ? 'Admin' : 'Reader'} · joined ${dateLabel(account.created_at)}</p></div>
          </div>
          <div class="account__stats">
            <div><b>${state.profile?.level || 1}</b><span>level</span></div>
            <div><b>${state.profile?.xp || 0}</b><span>XP</span></div>
            <div><b>${state.profile?.streak?.count || 0}</b><span>day streak</span></div>
            <div><b>${state.profile?.onboarded ? 'Yes' : 'Not yet'}</b><span>survey</span></div>
          </div>
          <div class="hstack" style="margin-top:1rem;flex-wrap:wrap">
            <a class="btn btn--sm btn--ghost" href="/profile" data-link>${raw(icons.user)} Profile & settings</a>
            <a class="btn btn--sm btn--ghost" href="/account" data-link>Account &amp; sync</a>
            <button class="btn btn--sm btn--ghost" data-logout>Sign out</button>
          </div>
          <p class="account__fine">This account is stored in the server’s SQLite file. Every new signup is recorded with its email and join date.</p>
        </div>

        <div class="card card-pad-lg">
          <h2 style="font-size:1.05rem">About this sign-in</h2>
          <ul class="account__list">
            <li>Works across browsers that can reach this server.</li>
            <li>No password reset — there is no mail server in this build.</li>
            <li>Your reading profile, saves, streak and settings stay attached to the account.</li>
            <li>Admins can download the full user list as a CSV file.</li>
          </ul>
        </div>
      </div>

      <div class="card card-pad-lg account__danger">
        <div class="between" style="gap:1rem">
          <div><h2 style="font-size:1rem">Delete account</h2><p class="tiny muted">Remove your email, profile, saves, notes and reading history from this server. The shared news archive stays.</p></div>
          <button class="btn btn--sm btn--danger" data-delete-account>Delete account</button>
        </div>
      </div>

      <p class="account__legal"><a href="/privacy" data-link>Privacy</a> · <a href="/terms" data-link>Terms</a> · <a href="mailto:support@pulse.local">Contact</a></p>

      ${account.is_admin ? html`
        <section class="section">
          <div class="section-head" style="margin-top:1.5rem">
            <h2>All users</h2>
            <a class="btn btn--sm btn--ghost" href="/api/admin/users.csv" download>Download CSV ${raw(icons.external)}</a>
          </div>
          <div class="card card-pad" id="admin-users"><p class="small muted">Loading accounts…</p></div>
        </section>` : ''}
    </div>`;
}

function bindDashboard(root, account) {
  root.querySelector('[data-delete-account]')?.addEventListener('click', () => {
    const input = document.createElement('input');
    input.type = 'password';
    input.autocomplete = 'current-password';
    input.placeholder = 'Your password';
    input.setAttribute('aria-label', 'Password');
    const body = document.createElement('div');
    body.innerHTML = html`<p class="small muted">This removes your account, email, profile, saves and reading history. It cannot be undone.</p>`;
    body.append(input);
    const { close } = modal({
      title: 'Delete your account?',
      body,
      actions: [
        { label: 'Cancel', class: 'btn--ghost' },
        {
          label: 'Delete forever',
          class: 'btn--danger',
          onClick: async () => {
            try {
              const result = await post('/api/auth/delete', { password: input.value });
              setAccount(null);
              if (result.profile) setProfile(result.profile);
              toast('Account deleted');
              close();
              navigate('/', { replace: true });
              return true;
            } catch (err) {
              toast(err.message || 'Could not delete the account.', { type: 'bad' });
              return false;
            }
          },
        },
      ],
    });
  });
  root.querySelector('[data-logout]')?.addEventListener('click', async () => {
    try {
      const result = await post('/api/auth/logout', {});
      setAccount(null);
      if (result.profile) setProfile(result.profile);
      toast('Signed out — this browser is a guest again');
      navigate('/', { replace: true });
    } catch (err) {
      toast(err.message || 'Could not sign out.', { type: 'bad' });
    }
  });
  void account;
}

async function loadUsers(root) {
  const slot = root.querySelector('#admin-users');
  if (!slot) return;
  try {
    const data = await get('/api/admin/users', 20);
    const users = data.users || [];
    slot.innerHTML = html`
      <div class="between" style="margin-bottom:.6rem">
        <p class="tiny muted">${users.length} account${users.length === 1 ? '' : 's'} recorded</p>
        <span class="badge badge--topic">stored in pulse.sqlite3</span>
      </div>
      <div class="admin-table-wrap">
        <table class="admin-table">
          <thead><tr><th>Email</th><th>Name</th><th>Joined</th><th>Last login</th><th>Onboarded</th><th>Level</th></tr></thead>
          <tbody>
            ${users.map((user) => html`
              <tr>
                <td><b>${user.email}</b>${user.is_admin ? html` <span class="badge badge--topic">admin</span>` : ''}</td>
                <td>${user.name || user.profile_name || '—'}</td>
                <td>${dateLabel(user.created_at)}</td>
                <td>${user.last_login_at ? timeAgo(user.last_login_at) : '—'}</td>
                <td>${user.onboarded ? 'Yes' : 'No'}</td>
                <td>${user.level || 1}</td>
              </tr>`)}
          </tbody>
        </table>
      </div>`;
  } catch (err) {
    slot.innerHTML = html`<p class="small muted">${err.message || 'Could not load users.'}</p>`;
  }
}
