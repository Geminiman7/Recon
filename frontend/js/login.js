async function login() {

    try {

        const response = await api(
            "/auth/login",
            "POST",
            {
                email: document.getElementById("email").value,
                password: document.getElementById("password").value
            }
        );

        window.location.href = "dashboard.html";

    } catch (error) {

        alert(error.message);

    }

}