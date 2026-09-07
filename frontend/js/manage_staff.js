protectPage();

loadUsers();

async function loadUsers(){
    try{
        const users = await api('/users/');
            const tbody = document.querySelector('#users tbody');
        tbody.innerHTML = '';

        users.forEach(u => {
            const tr = document.createElement('tr');
            [u.full_name, u.email, u.role, u.is_active ? "Yes" : "No", ""].forEach(value => {
                const cell = document.createElement("td");
                cell.textContent = value;
                tr.appendChild(cell);
            });

            // actions
            const actionsTd = tr.querySelector('td:last-child');

            const toggleBtn = document.createElement('button');
            toggleBtn.className = 'btn';
            toggleBtn.innerText = u.is_active ? 'Disable' : 'Enable';
            toggleBtn.onclick = () => toggleActive(u.id, u.is_active);

            const deleteBtn = document.createElement('button');
            deleteBtn.className = 'btn btn-danger';
            deleteBtn.style.marginLeft = '8px';
            deleteBtn.innerText = 'Delete';
            deleteBtn.onclick = () => deleteUser(u.id);

            actionsTd.appendChild(toggleBtn);
            actionsTd.appendChild(deleteBtn);

            tbody.appendChild(tr);
        });

    } catch(e){
        alert(e.message || 'Failed to load users');
    }
}

async function createUser(){
    try{
        const payload = {
            full_name: document.getElementById('full_name').value,
            email: document.getElementById('email').value,
            password: document.getElementById('password').value,
            role: document.getElementById('role').value
        };

        // basic validation
        if(!payload.full_name || !payload.email || !payload.password){
            alert('Full name, email and password are required.');
            return;
        }

        if(payload.password.length < 12){
            alert('Password must be at least 12 characters.');
            return;
        }

        const allowedRoles = ['Admin','Finance','Auditor','Viewer'];
        if(!allowedRoles.includes(payload.role)){
            alert('Invalid role selected.');
            return;
        }

        await api('/users/', 'POST', payload);

        // clear form
        document.getElementById('full_name').value = '';
        document.getElementById('email').value = '';
        document.getElementById('password').value = '';

        loadUsers();

        alert('User created');

    } catch(e){
        alert(e.message || 'Failed to create user');
    }
}

async function deleteUser(id){
    if(!confirm('Delete this user? This action cannot be undone.')) return;

    try{
        await api(`/users/${id}`, 'DELETE');
        await loadUsers();
        alert('User deleted.');
    } catch(e){
        alert(e.message || 'Failed to delete user');
    }
}

async function toggleActive(id, currentState){
    try{
        await api(`/users/${id}/active?active=${!currentState}`, 'PATCH');
        await loadUsers();
    } catch(e){
        alert(e.message || 'Failed to update user');
    }
}

// show current user name in topbar
async function loadMe(){
    try{
        const me = await api('/auth/me');
        document.getElementById('username').innerText = me.full_name;
    } catch(e){
        console.warn('Failed to load current user:', e.message);
    }
}

loadMe();
