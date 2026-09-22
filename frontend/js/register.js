async function registerCompany() {

    const passwordInput = document.getElementById("password");
    const passwordValue = passwordInput.value;
    if (Array.from(passwordValue).length < 12) {
        alert("Minimum password length is 12 characters.");
        passwordInput.focus();
        return;
    }

    try {

        const response = await api(
            "/auth/register",
            "POST",
            {
                company_name: company_name.value,
                company_email: company_email.value,
                phone: phone.value,
                address: address.value,
                admin_name: admin_name.value,
                admin_email: admin_email.value,
                password: passwordValue
            }
        );

        alert(response.message);

        window.location.href = "/login";

    } catch (error) {

        alert(error.message);

    }

}
