from captator import parser


def test_tokenize_text_1():
    text = """
    [Rank]
Secunda die infra Octavam Epiphaniæ;;Semiduplex;;5.6;;ex Sancti/01-06
    """
    tokenized = parser.Tokenizer(text)

    assert len(tokenized) == 17


def test_tokenize_text_2():
    text = """
    [Rule]
Gloria
CredoDA
Prefatio=Epi
Suffragium=Maria2;Papa;Ecclesia;;
Infra octavam Epiphaniæ Domini
    """
    tokenized = parser.Tokenizer(text)

    assert len(tokenized) == 18


def test_tokenize_text_3():
    text = """
    [Introitus]
!Malach 3:1; 1 Par 29:12
v. Ecce, advénit dominátor Dóminus: et regnum in manu ejus et potéstas et impérium.
!Ps 71:1
Deus, judícium tuum Regi da: et justítiam tuam Fílio Regis.
&Gloria
v. Ecce, advénit dominátor Dóminus: et regnum in manu ejus et potéstas et impérium.
    """
    tokenized = parser.Tokenizer(text)

    assert len(tokenized) == 60


def test_tokenize_text_4():
    text = """
    [Evangelium]
@Tempora/Nat2-0

[Offertorium]
@Tempora/Nat30

[Secreta]
@Commune/C2

[Commemoratio Secreta] (rubrica tridentina)
!Pro S. Stephano Protomartyre
@Sancti/08-03:Secreta
!Pro S. Joanne Evangelista
@Sancti/12-27:Secreta
!Pro Ss. Innocentibus
@Sancti/12-28:Secreta

[Communio]
@Tempora/Nat30
    """
    tokenized = parser.Tokenizer(text)

    assert len(tokenized) == 58
