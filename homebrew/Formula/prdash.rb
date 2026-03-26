class Prdash < Formula
  include Language::Python::Virtualenv

  desc "Terminal dashboard for monitoring GitHub PRs requiring your attention"
  homepage "https://github.com/prdash/prdash"
  url "https://files.pythonhosted.org/packages/source/p/prdash/prdash-0.1.0.tar.gz"
  sha256 "PLACEHOLDER_SHA256"
  license "MIT"

  depends_on "python@3.12"

  def install
    virtualenv_create(libexec, "python3.12")
    system libexec/"bin/pip", "install", "prdash==#{version}"
    bin.install_symlink Dir[libexec/"bin/prdash"]
  end

  test do
    assert_match version.to_s, shell_output("#{bin}/prdash --version")
  end
end
