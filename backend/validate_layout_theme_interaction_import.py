from app.services.ui_theme_layout_contract_service import build_layout_contract


def main() -> None:
    html = """
    <header>Brand</header>
    <nav class="mobile-menu">
      <a href="/search">Search</a>
      <a href="/browse">Browse</a>
      <a href="/patterns">UX/UI Patterns</a>
      <a href="/blog">Blog</a>
      <a href="/about">About</a>
      <a href="/submit">Submit UI Request</a>
    </nav>
    """
    css = """
    @media (max-width: 768px) {
      .mobile-menu-drawer { position: fixed; left: 0; width: 320px; transform: translateX(-100%); }
      .mobile-menu-overlay { background: rgba(0,0,0,.45); }
    }
    """
    contract = build_layout_contract(html, css)
    drawer = contract["mobile"]["drawer"]
    assert drawer["detected"] is True, contract
    assert drawer["side"] == "left", contract
    assert drawer["width"] == "320px", contract
    assert drawer["overlay"]["detected"] is True, contract
    assert contract["mobile"]["breakpoint"] == 768, contract
    assert contract["navigation"]["items"][:3] == ["Search", "Browse", "UX/UI Patterns"], contract
    assert contract["desktop"]["sidebar_present"] is False, contract

    right_css = ".offcanvas-menu{position:fixed;right:0;width:75%;transform:translateX(100%)}"
    right = build_layout_contract("<nav><a>Home</a></nav>", right_css)
    assert right["mobile"]["drawer"]["side"] == "right", right

    print("PASS: Layout + Theme + Interaction contract extraction")


if __name__ == "__main__":
    main()
